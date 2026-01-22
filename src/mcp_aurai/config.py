"""配置管理模块"""

import os
import re
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

load_dotenv()


class AuraiConfig(BaseModel):
    """上级AI配置"""

    # API提供商
    provider: Literal["zhipu", "openai", "anthropic", "gemini", "custom"] = Field(
        default_factory=lambda: os.getenv("AURAI_PROVIDER", "zhipu"),
        description="AI服务提供商"
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
        default_factory=lambda: os.getenv("AURAI_MODEL", "glm-4-flash"),
        description="模型名称"
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

    # 最大tokens
    max_tokens: int = Field(
        default=4096,
        ge=1,
        description="最大生成tokens"
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
