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

    def _build_messages_from_history(
        self,
        conversation_history: list[dict] | None,
    ) -> list[dict[str, str]]:
        """
        将对话历史转换为 AI API 的 messages 格式

        Args:
            conversation_history: 对话历史列表

        Returns:
            转换后的 messages 列表
        """
        if not conversation_history:
            return []

        messages = []

        # 首先处理所有 sync_context 类型的记录（作为 system 消息）
        for turn in conversation_history:
            if turn.get("type") == "sync_context":
                file_contents = turn.get("file_contents", {})
                if not file_contents:
                    continue

                # 为每个文件构建消息（可能拆分为多个片段）
                for file_path, content in file_contents.items():
                    chunks = self._split_file_content(file_path, content)

                    for idx, chunk in enumerate(chunks):
                        total = len(chunks)
                        if total == 1:
                            header = f"## 已上传文件\n\n### 文件: {file_path}\n"
                        else:
                            header = f"## 已上传文件 ({idx + 1}/{total})\n\n### 文件: {file_path} (第 {idx + 1}/{total} 部分)\n"

                        messages.append({
                            "role": "system",
                            "content": header + f"```\n{chunk}\n```"
                        })

        # 然后处理其他类型的对话历史
        for turn in conversation_history:
            # 跳过 sync_context（已处理）和 progress（不需要在消息中）
            if turn.get("type") in ("sync_context", "progress"):
                continue

            # 构建用户消息
            if turn.get("type") == "consult":
                user_content = f"问题类型: {turn.get('problem_type')}\n错误描述: {turn.get('error_message')}"
            else:
                user_content = "未知操作"

            messages.append({"role": "user", "content": user_content})

            # 构建助手回复
            response = turn.get("response", {})
            if response.get("analysis") or response.get("guidance"):
                assistant_content = f"分析: {response.get('analysis', '')}\n指导: {response.get('guidance', '')}"
                messages.append({"role": "assistant", "content": assistant_content})

        return messages

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

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加对话历史
        history_messages = self._build_messages_from_history(conversation_history)
        messages.extend(history_messages)

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        logger.info(f"发送请求到 {self.config.base_url}，消息数: {len(messages)}")

        try:
            response = self._client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
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
