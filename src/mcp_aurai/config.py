"""配置管理模块"""

import os
import re
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

load_dotenv()


# ============================================================================
# GLM-4.7 模型参数配置（基于智谱 GLM-4.7 规格的默认值）
# ============================================================================
# GLM-4.7 模型规格：
#   - 上下文窗口：200,000 tokens
#   - 最大输出：128,000 tokens
#
# 本配置采用 GLM-4.7 参数作为默认值，确保最佳性能和稳定性：
#   - context_window: 200,000（模型上限）
#   - max_message_tokens: 150,000（单条文件消息上限）
#   - max_tokens: 32,000（建议输出长度）
#
# 用户可通过环境变量覆盖这些默认值（适用于其他模型）
# ============================================================================

# 模型上下文窗口大小（tokens）- 默认基于 GLM-4.7 的 200K 上限
# 可通过 AURAI_CONTEXT_WINDOW 环境变量覆盖
DEFAULT_CONTEXT_WINDOW = 200000

# 单条消息最大 tokens（用于文件内容分批发送）
# 可通过 AURAI_MAX_MESSAGE_TOKENS 环境变量覆盖
DEFAULT_MAX_MESSAGE_TOKENS = 150000

# 最大输出 tokens（上级 AI 的回复长度）
# 可通过 AURAI_MAX_TOKENS 环境变量覆盖
DEFAULT_MAX_TOKENS = 32000


class AuraiConfig(BaseModel):
    """上级AI配置"""

    # API提供商（固定为 custom，使用 OpenAI 兼容 API）
    provider: Literal["custom"] = Field(
        default="custom",
        description="AI服务提供商（固定使用自定义 OpenAI 兼容 API）"
    )

    # API密钥
    api_key: str = Field(
        default_factory=lambda: os.getenv("AURAI_API_KEY", ""),
        description="API密钥"
    )

    # API基础URL（可选，用于代理或自定义端点）
    base_url: str | None = Field(
        default_factory=lambda: os.getenv("AURAI_BASE_URL"),
        description="API基础URL"
    )

    # 模型名称
    model: str = Field(
        default_factory=lambda: os.getenv("AURAI_MODEL", "gpt-4o"),
        description="模型名称"
    )

    # 上下文窗口大小（tokens）- 默认基于 GLM-4.7，可通过环境变量覆盖
    context_window: int = Field(
        default_factory=lambda: int(os.getenv("AURAI_CONTEXT_WINDOW", str(DEFAULT_CONTEXT_WINDOW))),
        ge=1,
        description="模型上下文窗口大小（默认：200,000，基于 GLM-4.7）"
    )

    # 单条消息最大 tokens - 默认基于 GLM-4.7，可通过环境变量覆盖
    max_message_tokens: int = Field(
        default_factory=lambda: int(os.getenv("AURAI_MAX_MESSAGE_TOKENS", str(DEFAULT_MAX_MESSAGE_TOKENS))),
        ge=1,
        description="单条消息最大 tokens（默认：150,000，基于 GLM-4.7 优化）"
    )

    # 最大迭代次数
    max_iterations: int = Field(
        default=10,
        description="最大迭代次数"
    )

    # 温度参数
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="温度参数"
    )

    # 最大生成 tokens - 默认基于 GLM-4.7，可通过环境变量覆盖
    max_tokens: int = Field(
        default_factory=lambda: int(os.getenv("AURAI_MAX_TOKENS", str(DEFAULT_MAX_TOKENS))),
        ge=1,
        description="最大生成 tokens（默认：32,000，基于 GLM-4.7 优化）"
    )

    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """验证API密钥格式"""
        if not v or not v.strip():
            raise ValueError("API密钥不能为空")

        v = v.strip()

        # 基本长度验证（大多数API密钥至少20个字符）
        if len(v) < 10:
            raise ValueError("API密钥长度不能少于10个字符")

        # 基本格式验证（不能包含空格或特殊控制字符）
        if re.search(r'[\s\n\r\t]', v):
            raise ValueError("API密钥不能包含空格或控制字符")

        return v

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        """验证Base URL格式"""
        if v is None or not v.strip():
            return None

        v = v.strip()

        # 基本URL格式验证
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Base URL 必须以 http:// 或 https:// 开头")

        # 简单的URL格式检查
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )

        if not url_pattern.match(v):
            raise ValueError(f"Base URL 格式无效: {v}")

        return v


class ServerConfig(BaseModel):
    """服务器配置"""

    # 服务器名称
    name: str = "Aurai Advisor"

    # 日志级别
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # 对话历史最大保存数
    max_history: int = Field(
        default_factory=lambda: int(os.getenv("AURAI_MAX_HISTORY", "50")),
        ge=1,
        le=200,
        description="对话历史最大保存数"
    )

    # 启用对话历史持久化
    enable_persistence: bool = Field(
        default_factory=lambda: os.getenv("AURAI_ENABLE_PERSISTENCE", "true").lower() == "true",
        description="是否启用对话历史持久化到文件"
    )

    # 对话历史文件路径（固定在用户目录）
    history_path: str = Field(
        default_factory=lambda: os.getenv(
            "AURAI_HISTORY_PATH",
            str(Path.home() / ".mcp-aurai" / "history.json")
        ),
        description="对话历史文件路径"
    )


# 全局配置实例
_config: AuraiConfig | None = None
_server_config: ServerConfig | None = None


def get_aurai_config() -> AuraiConfig:
    """获取上级AI配置"""
    global _config
    if _config is None:
        _config = AuraiConfig()
    return _config


def get_server_config() -> ServerConfig:
    """获取服务器配置"""
    global _server_config
    if _server_config is None:
        _server_config = ServerConfig()
    return _server_config


def reset_config():
    """重置配置（主要用于测试）"""
    global _config, _server_config
    _config = None
    _server_config = None
