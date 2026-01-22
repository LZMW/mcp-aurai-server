"""AI客户端模块 - 支持多种AI提供商"""

import json
import logging
from typing import Literal

from zhipuai import ZhipuAI

from .config import get_aurai_config

logger = logging.getLogger(__name__)

# 网络超时配置（秒）
DEFAULT_TIMEOUT = 30.0
HTTP_TIMEOUT = 60.0


class AuraiClient:
    """上级AI客户端"""

    def __init__(self, provider: str | None = None):
        """
        初始化AI客户端

        Args:
            provider: AI服务提供商，默认从配置读取
        """
        config = get_aurai_config()
        self.provider = provider or config.provider
        self.config = config

        # 初始化对应提供商的客户端
        if self.provider == "zhipu":
            self._init_zhipu()
        elif self.provider == "openai":
            self._init_openai()
        elif self.provider == "anthropic":
            self._init_anthropic()
        elif self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "custom":
            self._init_custom()
        else:
            raise ValueError(f"不支持的AI提供商: {self.provider}")

    def _init_zhipu(self):
        """初始化智谱AI客户端"""
        if not self.config.api_key:
            raise ValueError("未设置AURAI_API_KEY环境变量")
        self._zhipu_client = ZhipuAI(api_key=self.config.api_key)
        logger.info(f"智谱AI客户端已初始化，模型: {self.config.model}")

    def _init_openai(self):
        """初始化OpenAI客户端"""
        if not self.config.api_key:
            raise ValueError("未设置AURAI_API_KEY环境变量")

        from openai import OpenAI
        import httpx

        # 创建带有超时配置的HTTP客户端
        http_client = httpx.Client(
            timeout=httpx.Timeout(HTTP_TIMEOUT, connect=DEFAULT_TIMEOUT)
        )

        # 如果有自定义 base_url，使用它；否则使用默认
        kwargs = {
            "api_key": self.config.api_key,
            "http_client": http_client
        }
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url

        self._openai_client = OpenAI(**kwargs)
        logger.info(f"OpenAI客户端已初始化，模型: {self.config.model}，超时: {HTTP_TIMEOUT}s")

    def _init_anthropic(self):
        """初始化Anthropic客户端"""
        if not self.config.api_key:
            raise ValueError("未设置AURAI_API_KEY环境变量")

        from anthropic import Anthropic

        self._anthropic_client = Anthropic(
            api_key=self.config.api_key,
            timeout=DEFAULT_TIMEOUT
        )
        logger.info(f"Anthropic客户端已初始化，模型: {self.config.model}，超时: {DEFAULT_TIMEOUT}s")

    def _init_custom(self):
        """初始化自定义 OpenAI 兼容客户端"""
        if not self.config.api_key:
            raise ValueError("未设置AURAI_API_KEY环境变量")
        if not self.config.base_url:
            raise ValueError("自定义提供商必须设置 AURAI_BASE_URL 环境变量")

        from openai import OpenAI
        import httpx

        # 创建带有超时配置的HTTP客户端
        http_client = httpx.Client(
            timeout=httpx.Timeout(HTTP_TIMEOUT, connect=DEFAULT_TIMEOUT)
        )

        self._openai_client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            http_client=http_client
        )
        logger.info(f"自定义OpenAI兼容客户端已初始化，Base URL: {self.config.base_url}，模型: {self.config.model}，超时: {HTTP_TIMEOUT}s")

    def _init_gemini(self):
        """初始化Google Gemini客户端"""
        if not self.config.api_key:
            raise ValueError("未设置AURAI_API_KEY环境变量")

        import google.generativeai as genai
        genai.configure(api_key=self.config.api_key)
        self._genai = genai
        logger.info(f"Gemini客户端已初始化，模型: {self.config.model}")

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
        if self.provider == "zhipu":
            return await self._chat_zhipu(user_message, system_prompt, response_format, conversation_history)
        elif self.provider == "openai":
            return await self._chat_openai(user_message, system_prompt, response_format, conversation_history)
        elif self.provider == "anthropic":
            return await self._chat_anthropic(user_message, system_prompt, response_format, conversation_history)
        elif self.provider == "gemini":
            return await self._chat_gemini(user_message, system_prompt, response_format, conversation_history)
        elif self.provider == "custom":
            return await self._chat_openai(user_message, system_prompt, response_format, conversation_history)
        else:
            raise ValueError(f"不支持的AI提供商: {self.provider}")

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
        for turn in conversation_history:
            # 跳过 sync_context 类型的历史记录
            if turn.get("type") == "sync_context":
                continue

            # 构建用户消息
            if turn.get("type") == "consult":
                user_content = f"问题类型: {turn.get('problem_type')}\n错误描述: {turn.get('error_message')}"
            elif turn.get("type") == "progress":
                user_content = f"执行操作: {turn.get('actions_taken')}\n执行结果: {turn.get('result')}"
            else:
                user_content = "未知操作"

            messages.append({"role": "user", "content": user_content})

            # 构建助手回复
            response = turn.get("response", {})
            if response.get("analysis") or response.get("guidance"):
                assistant_content = f"分析: {response.get('analysis', '')}\n指导: {response.get('guidance', '')}"
                messages.append({"role": "assistant", "content": assistant_content})

        return messages

    async def _chat_zhipu(
        self,
        user_message: str,
        system_prompt: str | None = None,
        response_format: Literal["text", "json_object"] = "json_object",
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """
        使用智谱AI进行聊天

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词
            response_format: 响应格式
            conversation_history: 对话历史

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

        logger.info(f"发送请求到智谱AI，消息数: {len(messages)}")

        try:
            response = self._zhipu_client.chat.completions.create(
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
            logger.error(f"智谱AI请求失败: {e}")
            return {
                "analysis": f"请求失败: {str(e)}",
                "guidance": "请检查API密钥和网络连接",
                "action_items": [],
                "needs_another_iteration": False,
                "resolved": False,
                "requires_human_intervention": True,
            }

    async def _chat_openai(
        self,
        user_message: str,
        system_prompt: str | None = None,
        response_format: Literal["text", "json_object"] = "json_object",
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """
        使用 OpenAI 或兼容 API 进行聊天

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词
            response_format: 响应格式
            conversation_history: 对话历史

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

        logger.info(f"发送请求到 {self.provider}，消息数: {len(messages)}")

        try:
            response = self._openai_client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            content = response.choices[0].message.content
            logger.info(f"收到响应，长度: {len(content)}")

            # 尝试解析JSON（与智谱AI相同的逻辑）
            try:
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
            logger.error(f"{self.provider} 请求失败: {e}")
            return {
                "analysis": f"请求失败: {str(e)}",
                "guidance": "请检查API密钥、Base URL和网络连接",
                "action_items": [],
                "needs_another_iteration": False,
                "resolved": False,
                "requires_human_intervention": True,
            }

    async def _chat_anthropic(
        self,
        user_message: str,
        system_prompt: str | None = None,
        response_format: Literal["text", "json_object"] = "json_object",
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """
        使用 Anthropic (Claude) API 进行聊天

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词
            response_format: 响应格式
            conversation_history: 对话历史

        Returns:
            解析后的JSON响应
        """
        from .prompts import SYSTEM_PROMPT

        system_prompt = system_prompt or SYSTEM_PROMPT

        # 构建消息列表
        messages = []

        # 添加对话历史
        history_messages = self._build_messages_from_history(conversation_history)
        messages.extend(history_messages)

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        # Anthropic要求max_tokens在1-8192之间
        max_tokens = min(self.config.max_tokens, 8192)

        logger.info(f"发送请求到 Anthropic，模型: {self.config.model}，消息数: {len(messages)}")

        try:
            response = self._anthropic_client.messages.create(
                model=self.config.model,
                max_tokens=max_tokens,
                temperature=self.config.temperature,
                system=system_prompt,
                messages=messages
            )

            # 提取文本内容
            # Anthropic响应格式: content = [{type: "text", text: "..."}]
            content = ""
            for block in response.content:
                if block.type == "text":
                    content += block.text

            logger.info(f"收到响应，长度: {len(content)}")

            # 尝试解析JSON（与OpenAI、智谱AI相同的逻辑）
            try:
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
            # 区分不同类型的错误
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                logger.error(f"Anthropic API密钥错误: {e}")
                guidance_msg = "请检查AURAI_API_KEY是否正确设置"
            elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
                logger.error(f"Anthropic API限流: {e}")
                guidance_msg = "API调用频率过高，请稍后重试"
            elif "invalid" in error_msg.lower() and "model" in error_msg.lower():
                logger.error(f"Anthropic模型错误: {e}")
                guidance_msg = f"模型 {self.config.model} 不存在或无法访问"
            else:
                logger.error(f"Anthropic请求失败: {e}")
                guidance_msg = "请检查API密钥、网络连接和模型配置"

            return {
                "analysis": f"请求失败: {error_msg}",
                "guidance": guidance_msg,
                "action_items": [],
                "needs_another_iteration": False,
                "resolved": False,
                "requires_human_intervention": True,
            }

    async def _chat_gemini(
        self,
        user_message: str,
        system_prompt: str | None = None,
        response_format: Literal["text", "json_object"] = "json_object",
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """
        使用 Google Gemini API 进行聊天

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词
            response_format: 响应格式
            conversation_history: 对话历史

        Returns:
            解析后的JSON响应
        """
        from .prompts import SYSTEM_PROMPT

        system_prompt = system_prompt or SYSTEM_PROMPT

        # Gemini 不支持多轮对话的 messages 格式，将历史拼接到 prompt 中
        history_text = ""
        if conversation_history:
            history_messages = self._build_messages_from_history(conversation_history)
            if history_messages:
                history_text = "\n\n## 历史对话\n\n"
                for msg in history_messages:
                    role = "用户" if msg["role"] == "user" else "助手"
                    history_text += f"{role}: {msg['content']}\n\n"

        logger.info(f"发送请求到 Gemini，模型: {self.config.model}")

        try:
            # Gemini使用GenerativeModel
            model = self._genai.GenerativeModel(self.config.model)

            # 构建提示词（Geminisystem需要作为part）
            prompt = f"{system_prompt}{history_text}\n\n{user_message}"

            # 调用API
            response = await model.generate_content_async(prompt)
            content = response.text

            logger.info(f"收到响应，长度: {len(content)}")

            # 尝试解析JSON（与其他提供商相同的逻辑）
            try:
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
            # 区分不同类型的错误
            error_msg = str(e)
            if "api" in error_msg.lower() and "key" in error_msg.lower():
                logger.error(f"Gemini API密钥错误: {e}")
                guidance_msg = "请检查AURAI_API_KEY是否正确设置"
            elif "quota" in error_msg.lower() or "limit" in error_msg.lower():
                logger.error(f"Gemini API限流: {e}")
                guidance_msg = "API调用频率过高，请稍后重试"
            elif "model" in error_msg.lower():
                logger.error(f"Gemini模型错误: {e}")
                guidance_msg = f"模型 {self.config.model} 不存在或无法访问"
            else:
                logger.error(f"Gemini请求失败: {e}")
                guidance_msg = "请检查API密钥、网络连接和模型配置"

            return {
                "analysis": f"请求失败: {error_msg}",
                "guidance": guidance_msg,
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
    provider: str,
    api_key: str,
    base_url: str = ""
) -> list[str]:
    """
    动态获取AI提供商的模型列表

    Args:
        provider: AI服务提供商 (zhipu, openai, anthropic, gemini, custom)
        api_key: API密钥
        base_url: 自定义API地址（仅custom需要）

    Returns:
        模型名称/ID列表

    Raises:
        Exception: API调用失败
    """
    logger.info(f"获取 {provider} 的模型列表")

    try:
        if provider == "zhipu":
            # 智谱AI：使用OpenAI SDK的models.list()
            from openai import OpenAI
            client = OpenAI(
                api_key=api_key,
                base_url="https://open.bigmodel.cn/api/paas/v4/"
            )
            models = client.models.list()
            return [model.id for model in models.data]

        elif provider == "openai":
            # OpenAI：使用models.list()
            from openai import OpenAI
            kwargs = {"api_key": api_key}
            client = OpenAI(**kwargs)
            models = client.models.list()
            return [model.id for model in models.data]

        elif provider == "anthropic":
            # Anthropic：SDK暂不支持models API，返回常用模型列表
            return [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
                "claude-3-opus-20240229",
            ]

        elif provider == "gemini":
            # Gemini：使用list_models()
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            models = genai.list_models()
            # 过滤支持生成文本的模型
            return [
                model.name for model in models
                if "generate" in model.supported_generation_methods
            ]

        elif provider == "custom":
            # Custom OpenAI兼容：使用models.list()
            if not base_url:
                raise ValueError("自定义提供商必须提供base_url")

            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=base_url)
            models = client.models.list()
            return [model.id for model in models.data]

        else:
            raise ValueError(f"不支持的提供商: {provider}")

    except Exception as e:
        logger.error(f"获取{provider}模型列表失败: {e}")
        raise
