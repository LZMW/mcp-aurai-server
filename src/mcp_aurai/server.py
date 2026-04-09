"""MCP服务器主文件 - 上级顾问"""

from contextlib import contextmanager
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from pydantic import Field

from .config import get_aurai_config, get_server_config
from .llm import get_aurai_client
from .prompts import build_consult_prompt, build_progress_prompt
from .utils import optimize_context_for_sync, prepare_file_for_sync

# 配置日志
server_config = get_server_config()
logging.basicConfig(
    level=getattr(logging, server_config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# 创建MCP服务器
mcp = FastMCP(server_config.name)

# 默认会话标识
DEFAULT_SESSION_ID = "default"

# 按会话隔离的对话历史
_conversation_history: dict[str, list[dict[str, Any]]] = {}
_loaded_sessions: set[str] = set()

# 历史文件锁的轮询间隔（秒）
HISTORY_LOCK_RETRY_INTERVAL = 0.05

# 历史摘要条目的类型
SUMMARY_ENTRY_TYPE = "summary"

# 单条摘要信息的最大显示长度
SUMMARY_FIELD_LIMIT = 160


def _normalize_session_id(session_id: str | None) -> str:
    """规范化会话标识，确保旧调用默认落到 default 会话。"""
    if session_id is None:
        return DEFAULT_SESSION_ID

    normalized = str(session_id).strip()
    return normalized or DEFAULT_SESSION_ID


def _get_history_file_for_session(session_id: str | None) -> Path:
    """
    获取某个会话对应的历史文件路径。

    默认会话继续使用原始 history_path，保证兼容旧版本；
    其他会话写入同目录下的独立文件，避免不同线程互相污染。
    """
    normalized = _normalize_session_id(session_id)
    history_file = Path(server_config.history_path)

    if normalized == DEFAULT_SESSION_ID:
        return history_file

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized).strip("._-") or "session"
    safe_name = safe_name[:40]
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:8]
    return history_file.with_name(
        f"{history_file.stem}.{safe_name}.{digest}{history_file.suffix}"
    )


def _get_history_lock_file_for_session(session_id: str | None) -> Path:
    """获取某个会话的历史锁文件路径。"""
    history_file = _get_history_file_for_session(session_id)
    return history_file.with_name(f"{history_file.name}.lock")


@contextmanager
def _history_file_lock(session_id: str | None):
    """
    为某个会话的历史文件申请一个轻量级跨进程锁。

    实现方式是独占创建 `.lock` 文件。
    拿到锁后，其他进程只能等待或超时，避免同时读写把历史文件踩坏。
    """
    normalized = _normalize_session_id(session_id)
    lock_file = _get_history_lock_file_for_session(normalized)
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    deadline = time.monotonic() + server_config.history_lock_timeout
    lock_fd: int | None = None

    while True:
        try:
            lock_fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(lock_fd, f"{os.getpid()} {normalized}".encode("utf-8"))
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"等待历史文件锁超时: {lock_file}（>{server_config.history_lock_timeout}秒）"
                )
            time.sleep(HISTORY_LOCK_RETRY_INTERVAL)

    try:
        yield
    finally:
        if lock_fd is not None:
            try:
                os.close(lock_fd)
            except OSError:
                logger.debug("关闭历史文件锁句柄失败: %s", lock_file, exc_info=True)
        try:
            lock_file.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            logger.warning("删除历史文件锁失败: %s", lock_file, exc_info=True)


def _write_history_file_atomic(history_file: Path, history: list[dict[str, Any]]):
    """
    原子写入历史文件。

    先写入同目录临时文件，再用 replace 一次性替换正式文件，
    这样即便中途崩掉，也不容易留下半截 JSON。
    """
    history_file.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(history, ensure_ascii=False, indent=2)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=history_file.parent,
            prefix=f".{history_file.stem}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)

        os.replace(temp_path, history_file)
    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                logger.warning("清理历史临时文件失败: %s", temp_path, exc_info=True)


def _truncate_summary_text(value: Any, limit: int = SUMMARY_FIELD_LIMIT) -> str:
    """将任意值裁剪为适合放进历史摘要的短文本。"""
    if value is None:
        return ""

    if isinstance(value, str):
        text = value.strip()
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            text = str(value)

    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 1)] + "…"


def _summarize_history_entry(entry: dict[str, Any]) -> str:
    """将单条历史记录压缩成一句纪要。"""
    entry_type = entry.get("type", "unknown")

    if entry_type == SUMMARY_ENTRY_TYPE:
        covered = entry.get("covered_entry_count")
        prefix = f"更早摘要（覆盖 {covered} 条）" if covered else "更早摘要"
        return f"{prefix}: {_truncate_summary_text(entry.get('summary_text'), 240)}"

    if entry_type == "consult":
        response = entry.get("response", {})
        parts = [
            f"咨询：类型={entry.get('problem_type', 'unknown')}",
            f"错误={_truncate_summary_text(entry.get('error_message'))}",
        ]
        if entry.get("had_answers"):
            parts.append("已补充回答")
        if response.get("analysis"):
            parts.append(f"分析={_truncate_summary_text(response.get('analysis'))}")
        elif response.get("guidance"):
            parts.append(f"建议={_truncate_summary_text(response.get('guidance'))}")
        parts.append(f"resolved={'是' if response.get('resolved') else '否'}")
        return "；".join(parts)

    if entry_type == "progress":
        response = entry.get("response", {})
        parts = [
            f"进展：操作={_truncate_summary_text(entry.get('actions_taken'))}",
            f"结果={entry.get('result', 'unknown')}",
        ]
        if entry.get("new_error"):
            parts.append(f"新错误={_truncate_summary_text(entry.get('new_error'))}")
        if entry.get("feedback"):
            parts.append(f"反馈={_truncate_summary_text(entry.get('feedback'))}")
        if response.get("guidance"):
            parts.append(f"顾问建议={_truncate_summary_text(response.get('guidance'))}")
        parts.append(f"resolved={'是' if response.get('resolved') else '否'}")
        return "；".join(parts)

    if entry_type == "sync_context":
        files = entry.get("files", [])
        file_names = [Path(file).name for file in files[:3]]
        file_desc = ", ".join(file_names)
        if len(files) > 3:
            file_desc += f" 等{len(files)}个"

        project_info = entry.get("project_info", {})
        project_keys = ", ".join(list(project_info.keys())[:5]) if isinstance(project_info, dict) else ""

        parts = [f"上下文同步：operation={entry.get('operation', 'unknown')}"]
        if file_desc:
            parts.append(f"文件={file_desc}")
        if entry.get("temp_files"):
            parts.append(f"大内容缓存={len(entry.get('temp_files', []))}")
        if project_keys:
            parts.append(f"项目字段={project_keys}")
        return "；".join(parts)

    return f"{entry_type}：{_truncate_summary_text(entry)}"


def _build_history_summary_entry(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """将多条较早历史压成一条摘要记录。"""
    if not entries:
        return None

    type_counts: dict[str, int] = {}
    summary_lines: list[str] = []

    for entry in entries:
        entry_type = entry.get("type", "unknown")
        type_counts[entry_type] = type_counts.get(entry_type, 0) + 1
        summary_lines.append(f"- {_summarize_history_entry(entry)}")

    type_desc = "，".join(f"{entry_type}:{count}" for entry_type, count in type_counts.items())
    summary_text = (
        f"已压缩较早的 {len(entries)} 条历史记录。"
        f"{f' 来源类型：{type_desc}。' if type_desc else ''}\n"
        + "\n".join(summary_lines)
    )

    return {
        "type": SUMMARY_ENTRY_TYPE,
        "summary_text": summary_text,
        "covered_entry_count": len(entries),
        "covered_type_counts": type_counts,
    }


def _maybe_compact_history(session_id: str | None):
    """在历史记录变长时，自动把较早轮次压缩成摘要。"""
    if not server_config.enable_history_summary:
        return

    normalized = _normalize_session_id(session_id)
    history = _get_session_history(normalized)
    raw_indexes = [
        index for index, entry in enumerate(history)
        if entry.get("type") != SUMMARY_ENTRY_TYPE
    ]

    summary_slot_count = 1
    available_raw_slots = max(server_config.max_history - summary_slot_count, 0)
    keep_recent = min(server_config.history_summary_keep_recent, available_raw_slots)
    trigger_threshold = max(server_config.history_summary_trigger_entries, keep_recent + 1)

    if len(raw_indexes) <= trigger_threshold:
        return

    keep_indexes = set(raw_indexes[-keep_recent:]) if keep_recent else set()

    latest_sync_index = None
    for index in range(len(history) - 1, -1, -1):
        if history[index].get("type") == "sync_context":
            latest_sync_index = index
            break

    if latest_sync_index is not None and available_raw_slots > 0 and latest_sync_index not in keep_indexes:
        if len(keep_indexes) >= available_raw_slots:
            keep_indexes.remove(min(keep_indexes))
        keep_indexes.add(latest_sync_index)

    summary_source_indexes = [
        index for index in range(len(history))
        if index not in keep_indexes
    ]
    entries_to_summarize = [history[index] for index in summary_source_indexes]
    summary_entry = _build_history_summary_entry(entries_to_summarize)

    if not summary_entry:
        return

    new_history = [summary_entry]
    for index, entry in enumerate(history):
        if index in keep_indexes:
            new_history.append(entry)

    history[:] = new_history
    logger.info(
        "会话 %r 的较早历史已摘要化：压缩 %s 条，保留 %s 条原始记录",
        normalized,
        len(entries_to_summarize),
        len(new_history) - 1,
    )


def _ensure_session_loaded(session_id: str | None):
    """按需加载某个会话的历史记录。"""
    normalized = _normalize_session_id(session_id)
    if normalized in _loaded_sessions:
        return

    if server_config.enable_persistence:
        _conversation_history[normalized] = _load_history_from_file(normalized)
    else:
        _conversation_history[normalized] = []

    _loaded_sessions.add(normalized)


def _get_session_history(session_id: str | None) -> list[dict[str, Any]]:
    """获取某个会话的完整历史。"""
    normalized = _normalize_session_id(session_id)
    _ensure_session_loaded(normalized)
    return _conversation_history.setdefault(normalized, [])


def _get_history(session_id: str | None = None) -> list[dict[str, Any]]:
    """获取某个会话的对话历史。"""
    history = _get_session_history(session_id)
    return history[-server_config.max_history:]


def _clear_history(
    session_id: str | None,
    reason: str,
    log_prefix: str = "[历史]",
) -> int:
    """
    清空某个会话的对话历史，并在启用持久化时立即同步到文件。

    这能避免只清空内存、不更新历史文件，导致服务重启后旧历史“复活”。

    Args:
        session_id: 会话标识
        reason: 清空原因，写入日志便于排查
        log_prefix: 日志前缀

    Returns:
        清空前的历史条数
    """
    normalized = _normalize_session_id(session_id)
    history = _get_session_history(normalized)
    history_count = len(history)
    history.clear()

    if server_config.enable_persistence:
        _save_history_to_file(normalized)

    logger.info(f"{log_prefix} 会话 {normalized!r} 的对话历史已清空（清除 {history_count} 条记录）")
    if reason:
        logger.info(f"   原因: {reason}")

    return history_count


def _add_to_history(entry: dict[str, Any], session_id: str | None = None):
    """添加到某个会话的对话历史。"""
    normalized = _normalize_session_id(session_id)
    history = _get_session_history(normalized)
    history.append(entry)

    _maybe_compact_history(normalized)

    # 最终兜底，避免极端配置下历史条数仍超限
    while len(history) > server_config.max_history:
        if history and history[0].get("type") == SUMMARY_ENTRY_TYPE and len(history) > 1:
            history.pop(1)
        else:
            history.pop(0)

    # 保存到文件(如果启用持久化)
    if server_config.enable_persistence:
        _save_history_to_file(normalized)


def _load_history_from_file(session_id: str | None = None) -> list[dict[str, Any]]:
    """
    从文件加载某个会话的对话历史

    Returns:
        对话历史列表,如果加载失败返回空列表
    """
    if not server_config.enable_persistence:
        return []

    normalized = _normalize_session_id(session_id)
    history_file = _get_history_file_for_session(normalized)

    try:
        with _history_file_lock(normalized):
            # 文件不存在时返回空列表
            if not history_file.exists():
                logger.info(f"历史文件不存在: {history_file}")
                _write_history_file_atomic(history_file, [])
                return []

            # 读取并解析JSON
            content = history_file.read_text(encoding="utf-8")
            history = json.loads(content)

            if not isinstance(history, list):
                # 兼容旧版本或其他格式：如果内容是字典，尽量提取对应会话。
                if isinstance(history, dict):
                    if normalized == DEFAULT_SESSION_ID and isinstance(history.get(DEFAULT_SESSION_ID), list):
                        history = history[DEFAULT_SESSION_ID]
                    elif isinstance(history.get(normalized), list):
                        history = history[normalized]
                    elif (
                        isinstance(history.get("sessions"), dict)
                        and isinstance(history["sessions"].get(normalized), list)
                    ):
                        history = history["sessions"][normalized]
                    else:
                        logger.warning(f"历史文件格式错误,无法识别会话 {normalized!r} 的历史结构")
                        return []
                else:
                    logger.warning(f"历史文件格式错误,期望list,实际{type(history)}")
                    return []

        logger.info(f"从文件加载了 {len(history)} 条历史记录，会话: {normalized!r}")
        return history

    except json.JSONDecodeError as e:
        logger.error(f"历史文件JSON解析失败: {e}")
        return []
    except TimeoutError as e:
        logger.error(f"获取历史文件锁失败: {e}")
        return []
    except Exception as e:
        logger.error(f"加载历史文件失败: {e}")
        return []


def _save_history_to_file(session_id: str | None = None):
    """
    保存某个会话的对话历史到文件

    注意: 此函数应该在每次添加历史后调用
    如果保存失败,仅记录警告,不中断服务
    """
    if not server_config.enable_persistence:
        return

    normalized = _normalize_session_id(session_id)
    history_file = _get_history_file_for_session(normalized)
    history = _conversation_history.get(normalized, [])

    try:
        with _history_file_lock(normalized):
            _write_history_file_atomic(history_file, history)

        logger.debug(f"已保存会话 {normalized!r} 的 {len(history)} 条历史记录到文件")

    except TimeoutError as e:
        logger.warning(f"保存历史文件时获取锁失败: {e},继续使用内存模式")
    except Exception as e:
        logger.warning(f"保存历史文件失败: {e},继续使用内存模式")


@mcp.tool()
async def consult_aurai(
    problem_type: str = Field(
        description="问题类型: runtime_error, syntax_error, design_issue, other"
    ),
    error_message: str = Field(description="错误描述"),
    code_snippet: str | None = Field(default=None, description="相关代码片段"),
    context: Any = Field(default=None, description="上下文信息（支持 JSON 字符串或字典，会自动解析）"),
    attempts_made: str | None = Field(default=None, description="已尝试的解决方案"),
    answers_to_questions: str | None = Field(
        default=None,
        description="对上级顾问反问的回答（仅在多轮对话时使用）"
    ),
    is_new_question: bool = Field(
        default=False,
        description="[重要] 是否为新问题（新问题会清空之前的所有对话历史，确保干净的上下文）"
    ),
    session_id: str | None = Field(
        default=None,
        description="会话标识。留空时使用默认会话；建议不同任务/线程使用不同 session_id 隔离上下文。"
    ),
) -> dict[str, Any]:
    """
    请求上级AI的指导（支持交互对齐机制与多轮对话）

    这是核心工具，当本地AI遇到编程问题时调用此工具获取上级AI的指导建议。

    ---

    **🔗 相关工具**

    - **sync_context**：需要上传文档或代码时使用
      - 📄 上传文章、说明文档（.md/.txt）
      - 💻 **上传代码文件（避免内容被截断）** ⭐ 重要
      - 将 `.py/.js/.json` 等代码文件复制为 `.txt` 后上传

    - **report_progress**：执行上级 AI 建议后，使用此工具报告进度并获取下一步指导

    - **get_status**：查看当前对话状态、迭代次数、配置信息

    **💡 重要提示：避免内容被截断**

    如果 `code_snippet` 或 `context` 内容过长，**请使用 `sync_context` 上传文件**：

    ```python
    # 步骤 1：直接上传代码文件（会自动转成文本发送）
    sync_context(operation='incremental', files=['script.py'])

    # 步骤 2：告诉上级顾问文件已上传
    consult_aurai(
        error_message='请审查已上传的 script.py 文件'
    )
    ```

    **优势**：
    - ✅ 避免代码在 `context` 或 `answers_to_questions` 字段中被截断
    - ✅ 利用文件读取机制，完整传递内容
    - ✅ 支持任意大小的代码文件

    ---

    ## [重要] 何时开始新对话？

    **系统会自动检测**，但你也可以手动控制：

    - **自动清空**：当上一次对话返回 `resolved=true` 时，系统会自动清空历史
    - **手动清空**：如果你要讨论一个完全不同的新问题，设置 `is_new_question=true`

    **何时设置 `is_new_question=true`？**
    - [OK] 切换到完全不相关的项目/文件
    - [OK] 之前的问题已解决，现在遇到全新的问题
    - [OK] 发现上下文混乱，想重新开始
    - [X] 不要在同一个问题的多轮对话中使用

    ## 交互协议

    ### 1. 多轮对齐机制
    - **不要期待一次成功**：上级顾问可能会认为信息不足，返回反问问题
    - 仔细阅读 `questions_to_answer` 中的每个问题
    - 主动搜集信息（读取文件、检查日志、运行命令）
    - **再次调用** 此工具，将答案填入 `answers_to_questions` 参数

    ### 2. 首次调用
    必须提供：
    - `problem_type`：问题类型（runtime_error/syntax_error/design_issue/other）
    - `error_message`：清晰描述问题或错误
    - `context`：相关上下文（代码片段、环境信息、已尝试的方案）
    - `code_snippet`：相关代码（如果有）

    ### 3. 后续调用（当返回 status="need_info" 时）
    必须提供：
    - `answers_to_questions`：对上级顾问反问的详细回答
    - 保持其他参数不变（除非有新信息）

    ### 4. 诚实原则
    - **禁止瞎编**：如果不知道答案，诚实说明"未找到相关信息"
    - **禁止臆测**：不要在没有证据的情况下假设解决方案
    - 提供具体证据（文件路径、日志内容、错误堆栈）

    ## 响应格式

    ### 信息不足时 (status="need_info")
    ```json
    {
      "status": "need_info",
      "questions_to_answer": ["问题1", "问题2"],
      "instruction": "请搜集信息并再次调用"
    }
    ```

    ### 提供指导时 (status="success")
    ```json
    {
      "status": "success",
      "analysis": "问题分析",
      "guidance": "解决建议",
      "action_items": ["步骤1", "步骤2"],
      "resolved": false  // 是否已完全解决
    }
    ```

    ### 问题解决后
    当 `resolved=true` 时，对话历史会自动清空，下次查询将开始新对话。

    ### [自动] 新对话检测
    系统会自动检测新问题：
    - 如果上一次对话的 `resolved=true`，下次调用 `consult_aurai` 时会自动清空历史
    - 保证每个独立问题都有干净的上下文，避免干扰

    ### [重要] 明确标注新问题（可选参数）
    如果你想强制开始一个新对话，可以设置 `is_new_question=true`：
    - **效果**：立即清空所有之前的对话历史
    - **后果**：上级AI将无法看到之前的任何上下文
    - **使用场景**：
      - 之前的对话已完全无关
      - 想重新开始讨论一个全新的问题
      - 发现上下文混乱，想重置

    **示例**：
    ```python
    # 第一次咨询（问题A）
    consult_aurai(problem_type="runtime_error", error_message="...")

    # 继续讨论问题A...
    consult_aurai(answers_to_questions="...")

    # 切换到问题B（标注为新问题，清空历史）
    consult_aurai(
        problem_type="design_issue",
        error_message="...",
        is_new_question=True  # [注意] 会清空之前关于问题A的所有对话
    )
    ```
    """
    config = get_aurai_config()
    normalized_session_id = _normalize_session_id(session_id)
    session_history = _get_session_history(normalized_session_id)

    logger.info(
        "收到consult_aurai请求，问题类型: %s，是否新问题: %s，会话: %s",
        problem_type,
        is_new_question,
        normalized_session_id,
    )

    # [新问题] 处理新问题：两种方式触发清空历史
    # 方式1：明确标注 is_new_question=true
    # 方式2：自动检测（上一次对话已解决）
    should_clear_history = False
    clear_reason = ""

    if is_new_question:
        # 明确标注新问题
        should_clear_history = True
        clear_reason = "下级AI明确标注为新问题"
    elif session_history:
        # 自动检测：检查上一次对话是否已解决
        last_entry = session_history[-1]
        last_response = last_entry.get("response", {})

        if last_response.get("resolved", False):
            should_clear_history = True
            clear_reason = "上一次对话已解决（自动检测）"

    # 执行清空操作
    if should_clear_history:
        _clear_history(normalized_session_id, clear_reason, log_prefix="[新问题]")
        logger.info(f"   新问题: {problem_type} - {error_message[:100]}...")
        session_history = _get_session_history(normalized_session_id)

    # 解析 context 参数（支持 JSON 字符串或字典）
    parsed_context: dict[str, Any] = {}
    if context:
        if isinstance(context, str):
            try:
                parsed_context = json.loads(context)
                logger.debug("已解析 JSON 格式的 context")
            except json.JSONDecodeError as e:
                logger.warning(f"context JSON 解析失败: {e}，使用空字典")
                parsed_context = {}
        elif isinstance(context, dict):
            parsed_context = context

    # 构建提示词（如果有对反问的回答，加入上下文）
    current_context = parsed_context or {}
    if answers_to_questions:
        current_context["answers_to_questions"] = answers_to_questions

    prompt = build_consult_prompt(
        problem_type=problem_type,
        error_message=error_message,
        code_snippet=code_snippet,
        context=current_context,
        attempts_made=attempts_made,
        iteration=len(session_history),
        conversation_history=_get_history(normalized_session_id),
    )

    # 调用上级AI，传递对话历史
    client = get_aurai_client()
    response = await client.chat(
        user_message=prompt,
        conversation_history=_get_history(normalized_session_id)
    )

    # 记录到历史
    _add_to_history({
        "type": "consult",
        "problem_type": problem_type,
        "error_message": error_message,
        "response": response,
        "had_answers": answers_to_questions is not None,
    }, normalized_session_id)

    # 根据上级顾问的响应状态返回不同格式
    if response.get("status") == "aligning":
        # 模式 A: 信息不足，需要补充
        logger.info(f"上级顾问要求补充信息，问题数: {len(response.get('questions', []))}")
        return {
            "status": "need_info",
            "message": "[提示] 上级顾问认为信息不足，请回答以下问题：",
            "questions_to_answer": response.get("questions", []),
            "instruction": "请搜集信息，再次调用 consult_aurai，并将答案填入 'answers_to_questions' 字段。",
            # ⭐ 相关工具提示
            "related_tools_hint": {
                "sync_context": {
                    "description": "如果需要上传文档（.md/.txt）来补充上下文信息",
                    "example": "sync_context(operation='full_sync', files=['path/to/doc.md'])"
                }
            }
        }
    else:
        # 模式 B: 信息充足，提供指导
        logger.info(f"上级顾问提供指导，resolved: {response.get('resolved', False)}")

        # 检查问题是否已解决，若解决则清空对话历史
        if response.get("resolved", False):
            _clear_history(normalized_session_id, "上级顾问返回 resolved=true", log_prefix="[完成]")

        return {
            "status": "success",
            "analysis": response.get("analysis"),
            "guidance": response.get("guidance"),
            "action_items": response.get("action_items", []),
            "code_changes": response.get("code_changes", []),
            "verification": response.get("verification"),
            "needs_another_iteration": response.get("needs_another_iteration", False),
            "resolved": response.get("resolved", False),
            "requires_human_intervention": response.get("requires_human_intervention", False),
            "hint": "[提示] 如需咨询新问题，下次调用时设置 is_new_question=true。这将清空之前的所有对话历史（包括之前的问题和上级AI的指导），但当前这条新问题会正常处理并保留在新的对话中",
        }


@mcp.tool()
async def sync_context(
    operation: str = Field(
        description="操作类型: full_sync（完整同步）, incremental（增量添加）, clear（清空历史）"
    ),
    files: Any = Field(
        default=None,
        description="文件路径列表（支持 JSON 字符串或列表，会自动解析）。`.md/.txt` 会直接上传，代码/配置等文本文件会自动转换为 `.txt/.md` 后发送给上级顾问；明显的二进制文件会被跳过。"
    ),
    project_info: Any = Field(
        default=None,
        description="项目信息字典，可包含项目名称、技术栈、任务描述等任意字段（支持 JSON 字符串或字典，会自动解析）"
    ),
    session_id: str | None = Field(
        default=None,
        description="会话标识。留空时使用默认会话；建议不同任务/线程使用不同 session_id 隔离上下文。"
    ),
) -> dict[str, Any]:
    """
    同步代码上下文（支持上传 .md 和 .txt 文件，避免内容被截断）

    在第一次调用或上下文发生重大变化时使用，让上级AI了解当前项目的整体情况。

    ---

    **🎯 典型使用场景**

    ### 场景 1：上传文章供上级顾问评审

    ```python
    sync_context(
        operation='full_sync',
        files=['文章.md'],
        project_info={
            'task': 'article_review',
            'target_platform': 'GLM Coding 知识库'
        }
    )
    consult_aurai(
        problem_type='other',
        error_message='请评审以下投稿文章...',
        context={'请查看已上传的文章文件': '已通过 sync_context 上传'}
    )
    ```

    ### 场景 2：上传代码文件（避免内容被截断）⭐ 重要

    ```python
    # 问题：代码太长，在 context 字段中可能被截断
    # 解决：直接上传代码文件，系统会自动转成文本发送给上级顾问
    # 步骤 1：上传文件
    sync_context(
        operation='incremental',
        files=['src/main.py'],
        project_info={
            'description': '需要调试的代码',
            'language': 'Python'
        }
    )

    # 步骤 2：告诉上级顾问文件已上传
    consult_aurai(
        problem_type='runtime_error',
        error_message='请审查已上传的 src/main.py 文件，帮我找出bug',
        context={
            'file_location': '已通过 sync_context 上传',
            'expected_behavior': '应该输出...',
            'actual_behavior': '实际输出...'
        }
    )
    ```

    **优势**：
    - ✅ 避免代码在 `context` 或 `answers_to_questions` 字段中被截断
    - ✅ 利用 sync_context 的文件读取机制，完整传递内容
    - ✅ 上级顾问可以完整读取代码文件

    ### 场景 3：项目首次初始化

    ```python
    sync_context(
        operation='full_sync',
        files=['README.md', 'docs/说明文档.md'],
        project_info={
            'project_name': 'My Project',
            'tech_stack': 'Python + FastAPI'
        }
    )
    ```

    ---

    ## [注意] 文件上传限制

    **files 参数优先支持文本文件，会自动转换代码/配置文件为文本发送！**

    - [OK] 支持：`README.md`, `docs.txt`, `notes.md`, `main.py`, `config.json`, `docker-compose.yml` 等文本内容
    - [X] 跳过：图片、压缩包、可执行文件等明显二进制文件

    ## 使用场景

    1. **full_sync**: 完整同步，适合首次调用或项目重大变更
    2. **incremental**: 增量同步，适合添加新文件或更新
    3. **clear**: 清空对话历史

    ## Token优化

    当 project_info 中的单个字段超过 800 tokens 时，会自动：
    - 缓存到临时文件
    - 在对话历史中记录文件路径
    - 发送给上级AI时仍会读取完整内容

    ## 参数说明

    - `operation`: 操作类型（full_sync/incremental/clear）
    - `files`: 文件路径列表，文本/代码文件会自动转换为 `.txt/.md` 发送
    - `project_info`: 项目信息字典，可包含任意字段
    """
    normalized_session_id = _normalize_session_id(session_id)
    logger.info(f"收到sync_context请求，操作: {operation}，会话: {normalized_session_id}")

    # 解析 files 参数（支持 JSON 字符串或列表）
    parsed_files: list[str] = []
    if files:
        if isinstance(files, str):
            try:
                parsed_files = json.loads(files)
                logger.debug("已解析 JSON 格式的 files")
            except json.JSONDecodeError as e:
                logger.warning(f"files JSON 解析失败: {e}，使用空列表")
                parsed_files = []
        elif isinstance(files, list):
            parsed_files = files

    # 解析 project_info 参数（支持 JSON 字符串或字典）
    parsed_project_info: dict[str, Any] = {}
    if project_info:
        if isinstance(project_info, str):
            try:
                parsed_project_info = json.loads(project_info)
                logger.debug("已解析 JSON 格式的 project_info")
            except json.JSONDecodeError as e:
                logger.warning(f"project_info JSON 解析失败: {e}，使用空字典")
                parsed_project_info = {}
        elif isinstance(project_info, dict):
            parsed_project_info = project_info

    if operation == "clear":
        # 清空对话历史
        _clear_history(
            normalized_session_id,
            'sync_context(operation="clear")',
            log_prefix="[sync_context]",
        )
        return {
            "status": "success",
            "message": "对话历史已清空",
            "history_count": 0,
        }

    elif operation in ("full_sync", "incremental"):
        # 优化 project_info：将大内容转换为临时文件
        optimized_project_info, temp_files, large_contents_map = optimize_context_for_sync(
            parsed_project_info,
            operation
        )

        # 将临时文件添加到文件列表中，以便读取
        all_files = parsed_files + temp_files

        # 读取文件内容（文本文件会自动转成 .txt/.md 的发送名）
        file_contents: dict[str, str] = {}
        uploaded_files: list[dict[str, Any]] = []

        # 先添加大内容（从缓存文件中读取）
        file_contents.update(large_contents_map)

        # 再读取用户提供的文件
        skipped_files = []  # 记录跳过的文件
        for file_path in parsed_files:
            try:
                prepared = prepare_file_for_sync(file_path)
            except Exception as e:
                logger.error(f"[错误] 预处理文件失败 {file_path}: {e}")
                skipped_files.append({
                    "path": file_path,
                    "reason": f"预处理失败: {e}",
                })
                continue

            if prepared["status"] == "ok":
                target_path = prepared["target_path"]
                content = prepared["content"]
                file_contents[target_path] = content
                uploaded_files.append({
                    "original_path": prepared["original_path"],
                    "sent_as_path": target_path,
                    "encoding": prepared["encoding"],
                    "auto_converted": prepared["auto_converted"],
                })
                logger.info(
                    "[读取] 已读取文件: %s -> %s (%s 字符，编码: %s，自动转换: %s)",
                    prepared["original_path"],
                    target_path,
                    len(content),
                    prepared["encoding"],
                    prepared["auto_converted"],
                )
            else:
                reason = prepared.get("reason", "未知原因")
                logger.warning(f"[跳过] 跳过文件: {file_path} ({reason})")
                skipped_files.append({
                    "path": file_path,
                    "reason": reason,
                })

        if skipped_files:
            logger.warning(f"[跳过] 共跳过 {len(skipped_files)} 个文件: {skipped_files}")

        # 记录上下文信息（包含所有文件内容，供上级AI读取）
        entry = {
            "type": "sync_context",
            "operation": operation,
            "files": parsed_files,
            "uploaded_files": uploaded_files,
            "temp_files": temp_files,  # 记录临时文件
            "file_contents": file_contents,  # 所有文件内容
            "project_info": optimized_project_info or {},
        }
        _add_to_history(entry, normalized_session_id)

        auto_converted_count = sum(1 for item in uploaded_files if item["auto_converted"])
        logger.info(
            "上下文已同步，文件数: %s，成功读取: %s，自动转换: %s，创建临时文件: %s",
            len(all_files),
            len(uploaded_files) + len(large_contents_map),
            auto_converted_count,
            len(temp_files),
        )

        # 如果一个都没读到，并且存在跳过文件，则返回错误
        if skipped_files and not uploaded_files and not large_contents_map:
            logger.warning(f"[错误] 所有文件都未能同步: {skipped_files}")
            return {
                "status": "error",
                "message": f"❌ 没有可发送给上级顾问的文本文件: {skipped_files}",
                "skipped_files": skipped_files,
                "hint": "代码/配置等文本文件现在会自动转成 .txt/.md。若仍失败，通常是文件不存在或文件本身是二进制。",
                "files_count": len(all_files),
                "text_files_read": len(uploaded_files) + len(large_contents_map),
                "temp_files_created": len(temp_files),
            }

        # 构建返回消息
        message_parts = [f"上下文已同步 ({operation})"]
        if temp_files:
            message_parts.append(f"{len(temp_files)}个大内容已缓存")
        if auto_converted_count:
            message_parts.append(f"{auto_converted_count}个文件已自动转为文本")
        if skipped_files:
            message_parts.append(f"{len(skipped_files)}个文件已跳过")

        return {
            "status": "success",
            "message": "，".join(message_parts),
            "files_count": len(all_files),
            "text_files_read": len(uploaded_files) + len(large_contents_map),
            "temp_files_created": len(temp_files),
            "auto_converted_files": [item for item in uploaded_files if item["auto_converted"]],
            "uploaded_files": uploaded_files,
            "skipped_files": skipped_files,
            "history_count": len(_get_session_history(normalized_session_id)),
        }

    else:
        return {
            "status": "error",
            "message": f"未知的操作类型: {operation}",
        }


@mcp.tool()
async def report_progress(
    actions_taken: str = Field(description="已执行的行动"),
    result: str = Field(description="执行结果: success, failed, partial"),
    new_error: str | None = Field(default=None, description="新的错误信息"),
    feedback: str | None = Field(default=None, description="执行反馈"),
    session_id: str | None = Field(
        default=None,
        description="会话标识。留空时使用默认会话；建议不同任务/线程使用不同 session_id 隔离上下文。"
    ),
) -> dict[str, Any]:
    """
    报告执行进度，请求下一步指导

    在执行了上级AI的建议后，调用此工具报告结果，获取下一步指导。

    ---
    **使用场景**：执行上级 AI 建议后，报告执行结果并获取后续指导
    **参数**：actions_taken（已执行的行动）、result（success/failed/partial）、new_error（新错误）、feedback（反馈）
    """
    config = get_aurai_config()
    normalized_session_id = _normalize_session_id(session_id)
    session_history = _get_session_history(normalized_session_id)

    # 检查迭代次数
    iteration = len(session_history)
    if iteration >= config.max_iterations:
        logger.warning(f"达到最大迭代次数 ({config.max_iterations})，请求人工介入")
        return {
            "analysis": f"已达到最大迭代次数 ({config.max_iterations})",
            "guidance": "建议人工介入检查问题",
            "action_items": ["请人工审查当前状态"],
            "needs_another_iteration": False,
            "resolved": False,
            "requires_human_intervention": True,
        }

    logger.info(f"收到report_progress请求，结果: {result}，会话: {normalized_session_id}")

    # 构建提示词
    prompt = build_progress_prompt(
        iteration=iteration,
        actions_taken=actions_taken,
        result=result,
        new_error=new_error,
        feedback=feedback,
        conversation_history=_get_history(normalized_session_id),
    )

    # 调用上级AI，传递对话历史
    client = get_aurai_client()
    response = await client.chat(
        user_message=prompt,
        conversation_history=_get_history(normalized_session_id)
    )

    # 记录到历史
    _add_to_history({
        "type": "progress",
        "actions_taken": actions_taken,
        "result": result,
        "new_error": new_error,
        "feedback": feedback,
        "response": response,
    }, normalized_session_id)

    # 检查问题是否已解决，若解决则清空对话历史
    if response.get("resolved", False):
        _clear_history(normalized_session_id, "report_progress 返回 resolved=true", log_prefix="[完成]")

    logger.info(f"report_progress完成，resolved: {response.get('resolved', False)}")
    return response


@mcp.tool()
async def get_status(
    session_id: str | None = Field(
        default=None,
        description="会话标识。留空时使用默认会话。"
    ),
) -> dict[str, Any]:
    """
    获取当前状态

    返回当前对话状态、迭代次数、配置信息等。

    ---
    **返回内容**：conversation_history_count（对话历史数量）、max_iterations（最大迭代次数）、max_history（最大历史条数）、provider（AI提供商）、model（模型名称）
    """
    normalized_session_id = _normalize_session_id(session_id)
    return {
        "session_id": normalized_session_id,
        "conversation_history_count": len(_get_session_history(normalized_session_id)),
        "loaded_session_count": len(_loaded_sessions),
        "history_path": str(_get_history_file_for_session(normalized_session_id)),
        "max_iterations": get_aurai_config().max_iterations,
        "max_history": server_config.max_history,
        "provider": get_aurai_config().provider,
        "model": get_aurai_config().model,
    }


def main():
    """主入口函数"""
    global _conversation_history, _loaded_sessions

    logger.info(f"启动 {server_config.name} MCP服务器")
    logger.info(f"AI提供商: {get_aurai_config().provider}")
    logger.info(f"模型: {get_aurai_config().model}")

    # 初始化对话历史持久化
    _conversation_history = {}
    _loaded_sessions = set()
    if server_config.enable_persistence:
        _ensure_session_loaded(DEFAULT_SESSION_ID)
        logger.info(f"持久化已启用,默认历史文件: {server_config.history_path}")
    else:
        logger.info("持久化未启用,使用内存模式")

    mcp.run()


if __name__ == "__main__":
    main()
