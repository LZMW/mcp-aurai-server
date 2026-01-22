"""工具函数模块"""

import json
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Token估算阈值
MAX_TOKENS_BEFORE_FILE = 800

# 临时文件目录
TEMP_DIR = Path(tempfile.gettempdir()) / "mcp_aurai_files"


def estimate_tokens(text: str) -> int:
    """
    估算文本的token数量

    使用简单的启发式方法：英文约4字符/token，中文约1.5字符/token
    对于混合文本，取平均值

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


def should_convert_to_file(content: str, threshold: int = MAX_TOKENS_BEFORE_FILE) -> bool:
    """
    判断内容是否应该转换为文件

    Args:
        content: 内容文本
        threshold: token阈值

    Returns:
        是否应该转换
    """
    tokens = estimate_tokens(content)
    logger.debug(f"内容token估算: {tokens}, 阈值: {threshold}")
    return tokens > threshold


def save_content_to_file(content: str, file_type: str = "md") -> Path:
    """
    将内容保存到临时文件

    Args:
        content: 要保存的内容
        file_type: 文件类型 (md 或 txt)

    Returns:
        临时文件路径
    """
    # 确保临时目录存在
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # 生成唯一文件名
    file_id = str(uuid.uuid4())[:8]
    file_path = TEMP_DIR / f"context_{file_id}.{file_type}"

    # 写入内容
    file_path.write_text(content, encoding='utf-8')

    logger.info(f"已保存内容到临时文件: {file_path} ({len(content)} 字符)")
    return file_path


def cleanup_temp_files():
    """
    清理所有临时文件
    """
    if not TEMP_DIR.exists():
        return

    try:
        for file in TEMP_DIR.glob("context_*.*"):
            file.unlink()
        logger.info(f"已清理临时文件目录: {TEMP_DIR}")
    except Exception as e:
        logger.warning(f"清理临时文件失败: {e}")


def optimize_context_for_sync(
    project_info: dict[str, Any],
    operation: str = "full_sync"
) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    """
    优化同步上下文，将大内容转换为文件

    注意：文件仅用于本地缓存，实际发送给上级AI时仍会读取文件内容

    Args:
        project_info: 项目信息字典
        operation: 操作类型

    Returns:
        (优化后的项目信息, 创建的临时文件路径列表, 文件路径到内容的映射)
    """
    temp_files = []
    file_contents_map = {}  # 文件路径 -> 内容
    optimized_info = {}

    for key, value in project_info.items():
        # 只处理字符串类型的大内容
        if isinstance(value, str):
            # 检查是否需要转换为文件
            if should_convert_to_file(value):
                # 转换为临时文件
                file_path = save_content_to_file(value, "md")
                temp_files.append(str(file_path))
                file_contents_map[str(file_path)] = value

                # 在上下文中标记为已缓存
                optimized_info[key] = f"[大内容已缓存到文件: {file_path.name}]"
                logger.info(f"字段 '{key}' 内容过大({estimate_tokens(value)} tokens)，已缓存到文件")
            else:
                optimized_info[key] = value
        elif isinstance(value, dict):
            # 递归处理嵌套字典
            nested_optimized, nested_files, nested_contents = optimize_context_for_sync(value, operation)
            optimized_info[key] = nested_optimized
            temp_files.extend(nested_files)
            file_contents_map.update(nested_contents)
        elif isinstance(value, list):
            # 处理列表（暂时保留原样）
            optimized_info[key] = value
        else:
            # 其他类型直接保留
            optimized_info[key] = value

    return optimized_info, temp_files, file_contents_map
