"""AI客户端模块 - 使用 OpenAI 兼容 API"""

import json
import logging
from typing import Literal

from .config import get_aurai_config

logger = logging.getLogger(__name__)

# 网络超时配置（秒）
DEFAULT_TIMEOUT = 30.0
HTTP_TIMEOUT = 60.0


class AuraiClient:
    """上级AI客户端（OpenAI 兼容 API）"""

    def __init__(self):
        """
        初始化AI客户端
        """
        config = get_aurai_config()
        self.config = config
        self._init_client()

    def _init_client(self):
        """初始化 OpenAI 兼容客户端"""
        if not self.config.api_key:
            raise ValueError("未设置AURAI_API_KEY环境变量")
        if not self.config.base_url:
            raise ValueError("未设置AURAI_BASE_URL环境变量")

        from openai import OpenAI
        import httpx

        # 创建带有超时配置的HTTP客户端
        http_client = httpx.Client(
            timeout=httpx.Timeout(HTTP_TIMEOUT, connect=DEFAULT_TIMEOUT)
        )

        self._client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            http_client=http_client
        )
        logger.info(f"OpenAI兼容客户端已初始化，Base URL: {self.config.base_url}，模型: {self.config.model}，超时: {HTTP_TIMEOUT}s")

    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的token数量

        使用简单的启发式方法：英文约4字符/token，中文约1.5字符/token

        Args:
            text: 要估算的文本

        Returns:
            估算的token数量
        """
        if not text:
            return 0

        # 统计中文字符
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')

        # 统计非中文字符
        other_chars = len(text) - chinese_chars

        # 估算token数
        # 中文：约1.5字符/token
        # 英文/其他：约4字符/token
        tokens = int(chinese_chars / 1.5 + other_chars / 4)

        return tokens

    def _split_file_content(self, file_path: str, content: str) -> list[str]:
        """
        拆分大文件内容为多个片段，确保每个片段不超过 max_message_tokens

        Args:
            file_path: 文件路径
            content: 文件内容

        Returns:
            内容片段列表
        """
        max_tokens = self.config.max_message_tokens

        # 估算内容 token 数
        content_tokens = self._estimate_tokens(content)

        # 如果内容不大，直接返回
        if content_tokens <= max_tokens:
            return [content]

        # 需要拆分
        logger.info(f"文件 {file_path} 内容过大（约 {content_tokens} tokens），将拆分为多个片段")

        chunks = []
        # 按字符数大致拆分（粗略估算）
        # 假设平均每个 token 约 3 字符
        target_chars = max_tokens * 3

        for i in range(0, len(content), target_chars):
            chunk = content[i:i + target_chars]
            chunks.append(chunk)
            logger.debug(f"  片段 {len(chunks)}: 约 {self._estimate_tokens(chunk)} tokens")

        logger.info(f"文件 {file_path} 已拆分为 {len(chunks)} 个片段")
        return chunks

    def _serialize_for_message(self, value) -> str:
        """将结构化数据转换为便于发送给模型的文本。"""
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)

    def _estimate_message_tokens(self, message: dict[str, str]) -> int:
        """估算单条消息的 token 数量，额外计入角色与协议开销。"""
        content = message.get("content", "")
        role = message.get("role", "")
        return self._estimate_tokens(content) + self._estimate_tokens(role) + 6

    def _estimate_messages_tokens(self, messages: list[dict[str, str]]) -> int:
        """估算多条消息的总 token 数量。"""
        return sum(self._estimate_message_tokens(message) for message in messages)

    def _build_message_groups_from_history(
        self,
        conversation_history: list[dict] | None,
    ) -> list[dict[str, object]]:
        """
        将对话历史转换为按轮次分组的消息列表。

        Args:
            conversation_history: 对话历史列表

        Returns:
            转换后的消息分组列表
        """
        if not conversation_history:
            return []

        groups: list[dict[str, object]] = []

        for turn in conversation_history:
            group_messages: list[dict[str, str]] = []

            if turn.get("type") == "sync_context":
                project_info = turn.get("project_info", {})
                if project_info:
                    project_info_text = self._serialize_for_message(project_info)
                    chunks = self._split_file_content("project_info.json", project_info_text)

                    for idx, chunk in enumerate(chunks):
                        total = len(chunks)
                        if total == 1:
                            header = "## 已同步项目背景\n"
                        else:
                            header = f"## 已同步项目背景 ({idx + 1}/{total})\n"

                        group_messages.append({
                            "role": "system",
                            "content": header + f"```json\n{chunk}\n```"
                        })

                file_contents = turn.get("file_contents", {})
                if file_contents:
                    for file_path, content in file_contents.items():
                        chunks = self._split_file_content(file_path, content)

                        for idx, chunk in enumerate(chunks):
                            total = len(chunks)
                            if total == 1:
                                header = f"## 已上传文件\n\n### 文件: {file_path}\n"
                            else:
                                header = f"## 已上传文件 ({idx + 1}/{total})\n\n### 文件: {file_path} (第 {idx + 1}/{total} 部分)\n"

                            group_messages.append({
                                "role": "system",
                                "content": header + f"```\n{chunk}\n```"
                            })

            elif turn.get("type") == "progress":
                continue

            else:
                if turn.get("type") == "consult":
                    user_content = f"问题类型: {turn.get('problem_type')}\n错误描述: {turn.get('error_message')}"
                else:
                    user_content = "未知操作"

                group_messages.append({"role": "user", "content": user_content})

                response = turn.get("response", {})
                if response.get("analysis") or response.get("guidance"):
                    assistant_content = f"分析: {response.get('analysis', '')}\n指导: {response.get('guidance', '')}"
                    group_messages.append({"role": "assistant", "content": assistant_content})

            if group_messages:
                groups.append({
                    "type": turn.get("type", "unknown"),
                    "messages": group_messages,
                })

        return groups

    def _build_messages_from_history(
        self,
        conversation_history: list[dict] | None,
    ) -> list[dict[str, str]]:
        """将对话历史转换为平铺的 messages 列表。"""
        groups = self._build_message_groups_from_history(conversation_history)

        messages: list[dict[str, str]] = []
        for group in groups:
            messages.extend(group["messages"])

        return messages

    def _truncate_messages_to_budget(
        self,
        messages: list[dict[str, str]],
        budget: int,
    ) -> list[dict[str, str]]:
        """
        在预算内尽量保留一组消息的前半部分。

        对于超大的文件同步记录，这比整组丢弃更实用，至少能保住项目背景和开头内容。
        """
        if budget <= 0:
            return []

        selected: list[dict[str, str]] = []
        used_tokens = 0

        for message in messages:
            message_tokens = self._estimate_message_tokens(message)
            if used_tokens + message_tokens > budget:
                break

            selected.append(message)
            used_tokens += message_tokens

        return selected

    def _select_history_messages_within_budget(
        self,
        history_groups: list[dict[str, object]],
        budget: int,
    ) -> tuple[list[dict[str, str]], bool]:
        """
        在预算内挑选历史消息。

        策略：
        1. 优先保留最近一次 sync_context，避免文件上下文先被挤掉；
        2. 再按时间倒序保留其他完整轮次；
        3. 如果最近一次 sync_context 太大，允许保留其前半部分。
        """
        if budget <= 0 or not history_groups:
            return [], bool(history_groups)

        selected_by_index: dict[int, list[dict[str, str]]] = {}
        trimmed = False

        latest_sync_index = None
        for index in range(len(history_groups) - 1, -1, -1):
            if history_groups[index].get("type") == "sync_context":
                latest_sync_index = index
                break

        if latest_sync_index is not None:
            latest_sync_messages = history_groups[latest_sync_index]["messages"]
            latest_sync_tokens = self._estimate_messages_tokens(latest_sync_messages)

            if latest_sync_tokens <= budget:
                selected_by_index[latest_sync_index] = latest_sync_messages
                budget -= latest_sync_tokens
            else:
                truncated_messages = self._truncate_messages_to_budget(latest_sync_messages, budget)
                if truncated_messages:
                    selected_by_index[latest_sync_index] = truncated_messages
                    budget -= self._estimate_messages_tokens(truncated_messages)
                trimmed = True

        for index in range(len(history_groups) - 1, -1, -1):
            if index == latest_sync_index:
                continue

            group_messages = history_groups[index]["messages"]
            group_tokens = self._estimate_messages_tokens(group_messages)

            if group_tokens <= budget:
                selected_by_index[index] = group_messages
                budget -= group_tokens
            else:
                trimmed = True

        selected_messages: list[dict[str, str]] = []
        for index in range(len(history_groups)):
            group_messages = selected_by_index.get(index)
            if group_messages:
                selected_messages.extend(group_messages)

        return selected_messages, trimmed

    def _fit_messages_to_context_window(
        self,
        base_messages: list[dict[str, str]],
        history_groups: list[dict[str, object]],
        current_user_message: dict[str, str],
    ) -> tuple[list[dict[str, str]], int, int]:
        """
        将请求消息压进上下文窗口，并动态计算可用输出长度。

        Returns:
            (最终消息列表, 估算输入 tokens, 实际输出上限)
        """
        reserved_output_tokens = min(self.config.max_tokens, max(self.config.context_window, 1))
        target_prompt_budget = max(self.config.context_window - reserved_output_tokens, 1)

        required_messages = [*base_messages, current_user_message]
        required_prompt_tokens = self._estimate_messages_tokens(required_messages)
        remaining_history_budget = max(target_prompt_budget - required_prompt_tokens, 0)

        selected_history_messages, trimmed = self._select_history_messages_within_budget(
            history_groups,
            remaining_history_budget,
        )

        final_messages = [*base_messages, *selected_history_messages, current_user_message]
        prompt_tokens = self._estimate_messages_tokens(final_messages)
        available_output_tokens = max(self.config.context_window - prompt_tokens, 1)
        response_max_tokens = min(self.config.max_tokens, available_output_tokens)

        if trimmed:
            logger.warning(
                "上下文窗口不足，已裁剪部分历史消息。输入约 %s tokens，窗口上限 %s，输出上限调整为 %s",
                prompt_tokens,
                self.config.context_window,
                response_max_tokens,
            )
        elif response_max_tokens < self.config.max_tokens:
            logger.info(
                "为适配上下文窗口，输出上限已从 %s 调整为 %s",
                self.config.max_tokens,
                response_max_tokens,
            )

        return final_messages, prompt_tokens, response_max_tokens

    async def chat(
        self,
        user_message: str,
        system_prompt: str | None = None,
        response_format: Literal["text", "json_object"] = "json_object",
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """
        发送聊天请求

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词
            response_format: 响应格式
            conversation_history: 对话历史（用于多轮对话）

        Returns:
            解析后的JSON响应
        """
        from .prompts import SYSTEM_PROMPT

        system_prompt = system_prompt or SYSTEM_PROMPT

        base_messages = []
        if system_prompt:
            base_messages.append({"role": "system", "content": system_prompt})

        history_groups = self._build_message_groups_from_history(conversation_history)
        current_user_message = {"role": "user", "content": user_message}
        messages, prompt_tokens, response_max_tokens = self._fit_messages_to_context_window(
            base_messages,
            history_groups,
            current_user_message,
        )

        logger.info(
            "发送请求到 %s，消息数: %s，估算输入 tokens: %s，输出上限: %s",
            self.config.base_url,
            len(messages),
            prompt_tokens,
            response_max_tokens,
        )

        try:
            response = self._client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=response_max_tokens,
            )

            content = response.choices[0].message.content
            logger.info(f"收到响应，长度: {len(content)}")

            # 尝试解析JSON
            try:
                # 清理可能存在的markdown代码块标记
                content_clean = content.strip()
                if content_clean.startswith("```json"):
                    content_clean = content_clean[7:]
                if content_clean.startswith("```"):
                    content_clean = content_clean[3:]
                if content_clean.endswith("```"):
                    content_clean = content_clean[:-3]
                content_clean = content_clean.strip()

                result = json.loads(content_clean)
                logger.info("成功解析JSON响应")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"JSON解析失败: {e}，返回原始文本")
                return {
                    "analysis": "解析失败",
                    "guidance": content,
                    "action_items": [],
                    "needs_another_iteration": False,
                    "resolved": False,
                    "requires_human_intervention": True,
                }

        except Exception as e:
            logger.error(f"API请求失败: {e}")
            return {
                "analysis": f"请求失败: {str(e)}",
                "guidance": "请检查API密钥、Base URL和网络连接",
                "action_items": [],
                "needs_another_iteration": False,
                "resolved": False,
                "requires_human_intervention": True,
            }


# 全局客户端实例
_client: AuraiClient | None = None


def get_aurai_client() -> AuraiClient:
    """获取AI客户端实例"""
    global _client
    if _client is None:
        _client = AuraiClient()
    return _client


def reset_client():
    """重置客户端（主要用于测试）"""
    global _client
    _client = None


def get_models(
    api_key: str,
    base_url: str,
) -> list[str]:
    """
    动态获取模型的列表

    Args:
        api_key: API密钥
        base_url: API地址

    Returns:
        模型名称/ID列表

    Raises:
        Exception: API调用失败
    """
    logger.info(f"获取模型列表，Base URL: {base_url}")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        models = client.models.list()
        return [model.id for model in models.data]

    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        raise
