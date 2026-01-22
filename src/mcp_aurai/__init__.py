"""上级顾问 MCP 服务器

让本地AI能够获取远程AI的指导，通过迭代式对话解决编程问题。
"""

__version__ = "0.1.0"

from .config import get_aurai_config, get_server_config
from .llm import get_aurai_client
from .server import mcp

__all__ = [
    "mcp",
    "get_aurai_config",
    "get_server_config",
    "get_aurai_client",
]
