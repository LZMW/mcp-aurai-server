"""MCP服务器主文件 - 上级顾问"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from pydantic import Field

from .config import get_aurai_config, get_server_config
from .llm import get_aurai_client
from .prompts import build_consult_prompt, build_progress_prompt
from .utils import optimize_context_for_sync

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

# 对话历史（用于迭代式问题解决）
_conversation_history: list[dict[str, Any]] = []


def _get_history() -> list[dict[str, Any]]:
    """获取对话历史"""
    return _conversation_history[-server_config.max_history:]


def _add_to_history(entry: dict[str, Any]):
    """添加到对话历史"""
    _conversation_history.append(entry)
    # 限制历史大小
    if len(_conversation_history) > server_config.max_history:
        _conversation_history.pop(0)

    # 保存到文件(如果启用持久化)
    if server_config.enable_persistence:
        _save_history_to_file()


def _load_history_from_file() -> list[dict[str, Any]]:
    """
    从文件加载对话历史

    Returns:
        对话历史列表,如果加载失败返回空列表
    """
    if not server_config.enable_persistence:
        return []

    history_file = Path(server_config.history_path)

    try:
        # 文件不存在时返回空列表
        if not history_file.exists():
            logger.info(f"历史文件不存在: {history_file}")
            # 创建目录
            history_file.parent.mkdir(parents=True, exist_ok=True)
            # 创建空文件
            history_file.write_text("[]", encoding="utf-8")
            return []

        # 读取并解析JSON
        content = history_file.read_text(encoding="utf-8")
        history = json.loads(content)

        # 验证类型
        if not isinstance(history, list):
            logger.warning(f"历史文件格式错误,期望list,实际{type(history)}")
            return []

        logger.info(f"从文件加载了 {len(history)} 条历史记录")
        return history

    except json.JSONDecodeError as e:
        logger.error(f"历史文件JSON解析失败: {e}")
        return []
    except Exception as e:
        logger.error(f"加载历史文件失败: {e}")
        return []


def _save_history_to_file():
    """
    保存对话历史到文件

    注意: 此函数应该在每次添加历史后调用
    如果保存失败,仅记录警告,不中断服务
    """
    if not server_config.enable_persistence:
        return

    history_file = Path(server_config.history_path)

    try:
        # 确保目录存在
        history_file.parent.mkdir(parents=True, exist_ok=True)

        # 保存为格式化的JSON(可读性好)
        history_file.write_text(
            json.dumps(_conversation_history, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        logger.debug(f"已保存 {len(_conversation_history)} 条历史记录到文件")

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
    # 步骤 1：将代码文件复制为 .txt
    shutil.copy('script.py', 'script.txt')

    # 步骤 2：上传文件
    sync_context(operation='incremental', files=['script.txt'])

    # 步骤 3：告诉上级顾问文件已上传
    consult_aurai(
        error_message='请审查已上传的 script.txt 文件'
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

    logger.info(f"收到consult_aurai请求，问题类型: {problem_type}，是否新问题: {is_new_question}")

    # [新问题] 处理新问题：两种方式触发清空历史
    # 方式1：明确标注 is_new_question=true
    # 方式2：自动检测（上一次对话已解决）
    should_clear_history = False
    clear_reason = ""

    if is_new_question:
        # 明确标注新问题
        should_clear_history = True
        clear_reason = "下级AI明确标注为新问题"
    elif _conversation_history:
        # 自动检测：检查上一次对话是否已解决
        last_entry = _conversation_history[-1]
        last_response = last_entry.get("response", {})

        if last_response.get("resolved", False):
            should_clear_history = True
            clear_reason = "上一次对话已解决（自动检测）"

    # 执行清空操作
    if should_clear_history:
        history_count = len(_conversation_history)
        _conversation_history.clear()
        logger.info(f"[新问题] 清空对话历史（清除 {history_count} 条记录）")
        logger.info(f"   原因: {clear_reason}")
        logger.info(f"   新问题: {problem_type} - {error_message[:100]}...")

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
        iteration=len(_conversation_history),
        conversation_history=_get_history(),
    )

    # 调用上级AI，传递对话历史
    client = get_aurai_client()
    response = await client.chat(
        user_message=prompt,
        conversation_history=_get_history()
    )

    # 记录到历史
    _add_to_history({
        "type": "consult",
        "problem_type": problem_type,
        "error_message": error_message,
        "response": response,
        "had_answers": answers_to_questions is not None,
    })

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
            history_count = len(_conversation_history)
            _conversation_history.clear()
            logger.info(f"[完成] 问题已解决，已清空对话历史（清除了 {history_count} 条记录）")

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
        description="**⚠️ 只支持 .txt 和 .md 文件！** 如需上传代码文件（.py/.js/.json等），必须先复制为 .txt。示例: shutil.copy('script.py', 'script.txt') 然后传 files=['script.txt']。文件路径列表（支持 JSON 字符串或列表，会自动解析）"
    ),
    project_info: Any = Field(
        default=None,
        description="项目信息字典，可包含项目名称、技术栈、任务描述等任意字段（支持 JSON 字符串或字典，会自动解析）"
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
    # 解决：将代码转换为 .txt 文件后上传

    import shutil

    # 步骤 1：将代码文件复制为 .txt
    shutil.copy('src/main.py', 'src/main.txt')

    # 步骤 2：上传文件
    sync_context(
        operation='incremental',
        files=['src/main.txt'],
        project_info={
            'description': '需要调试的代码',
            'language': 'Python'
        }
    )

    # 步骤 3：告诉上级顾问文件已上传
    consult_aurai(
        problem_type='runtime_error',
        error_message='请审查已上传的 src/main.txt 文件，帮我找出bug',
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

    **files 参数只支持 .txt 和 .md 文件！**

    - [OK] 支持：`README.md`, `docs.txt`, `notes.md` 等文本和Markdown文件
    - [X] 不支持：`.py`, `.js`, `.json`, `.yaml` 等代码文件

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
    - `files`: 文件路径列表，**只能是 .txt 或 .md 文件**
    - `project_info`: 项目信息字典，可包含任意字段
    """
    logger.info(f"收到sync_context请求，操作: {operation}")

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
        _conversation_history.clear()
        logger.info("对话历史已清空")
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

        # 读取文件内容（.txt 和 .md 文件）
        file_contents: dict[str, str] = {}

        # 先添加大内容（从缓存文件中读取）
        file_contents.update(large_contents_map)

        # 再读取用户提供的文件
        skipped_files = []  # 记录跳过的文件
        for file_path in parsed_files:
            path = Path(file_path)

            # [注意] 限制：只读取 .txt 和 .md 文件
            if path.suffix.lower() in ['.txt', '.md']:
                try:
                    if path.exists():
                        content = path.read_text(encoding='utf-8')
                        file_contents[file_path] = content
                        logger.info(f"[读取] 已读取文件: {file_path} ({len(content)} 字符)")
                    else:
                        logger.warning(f"[错误] 文件不存在: {file_path}")
                except Exception as e:
                    logger.error(f"[错误] 读取文件失败 {file_path}: {e}")
            else:
                # 不支持的文件类型
                logger.warning(f"[跳过] 跳过不支持的文件类型: {file_path} (仅支持 .txt 和 .md)")
                skipped_files.append(file_path)

        # 如果有跳过的文件，记录警告
        if skipped_files:
            logger.warning(f"[跳过] 共跳过 {len(skipped_files)} 个不支持的文件（仅支持 .txt 和 .md）: {skipped_files}")

        # 记录上下文信息（包含所有文件内容，供上级AI读取）
        entry = {
            "type": "sync_context",
            "operation": operation,
            "files": parsed_files,
            "temp_files": temp_files,  # 记录临时文件
            "file_contents": file_contents,  # 所有文件内容
            "project_info": optimized_project_info or {},
        }
        _add_to_history(entry)

        logger.info(f"上下文已同步，文件数: {len(all_files)}，读取文本文件: {len(file_contents)}，创建临时文件: {len(temp_files)}")

        # 如果有跳过的文件，返回错误状态
        if skipped_files:
            logger.warning(f"[错误] 跳过了不支持的文件类型: {skipped_files}")
            return {
                "status": "error",
                "message": f"❌ 文件类型不支持，请转换为 .txt 后重试: {skipped_files}",
                "skipped_files": skipped_files,
                "hint": "sync_context 只支持 .txt 和 .md 文件。代码文件请先: shutil.copy('xxx.py', 'xxx.txt')",
                "supported_types": [".txt", ".md"],
                "files_count": len(all_files),
                "text_files_read": len(file_contents),
                "temp_files_created": len(temp_files),
            }

        # 构建返回消息
        message_parts = [f"上下文已同步 ({operation})"]
        if temp_files:
            message_parts.append(f"{len(temp_files)}个大内容已缓存")

        return {
            "status": "success",
            "message": "，".join(message_parts),
            "files_count": len(all_files),
            "text_files_read": len(file_contents),
            "temp_files_created": len(temp_files),
            "history_count": len(_conversation_history),
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
) -> dict[str, Any]:
    """
    报告执行进度，请求下一步指导

    在执行了上级AI的建议后，调用此工具报告结果，获取下一步指导。

    ---
    **使用场景**：执行上级 AI 建议后，报告执行结果并获取后续指导
    **参数**：actions_taken（已执行的行动）、result（success/failed/partial）、new_error（新错误）、feedback（反馈）
    """
    config = get_aurai_config()

    # 检查迭代次数
    iteration = len(_conversation_history)
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

    logger.info(f"收到report_progress请求，结果: {result}")

    # 构建提示词
    prompt = build_progress_prompt(
        iteration=iteration,
        actions_taken=actions_taken,
        result=result,
        new_error=new_error,
        feedback=feedback,
        conversation_history=_get_history(),
    )

    # 调用上级AI，传递对话历史
    client = get_aurai_client()
    response = await client.chat(
        user_message=prompt,
        conversation_history=_get_history()
    )

    # 记录到历史
    _add_to_history({
        "type": "progress",
        "actions_taken": actions_taken,
        "result": result,
        "new_error": new_error,
        "feedback": feedback,
        "response": response,
    })

    # 检查问题是否已解决，若解决则清空对话历史
    if response.get("resolved", False):
        history_count = len(_conversation_history)
        _conversation_history.clear()
        logger.info(f"[完成] 问题已解决，已清空对话历史（清除了 {history_count} 条记录）")

    logger.info(f"report_progress完成，resolved: {response.get('resolved', False)}")
    return response


@mcp.tool()
async def get_status() -> dict[str, Any]:
    """
    获取当前状态

    返回当前对话状态、迭代次数、配置信息等。

    ---
    **返回内容**：conversation_history_count（对话历史数量）、max_iterations（最大迭代次数）、max_history（最大历史条数）、provider（AI提供商）、model（模型名称）
    """
    return {
        "conversation_history_count": len(_conversation_history),
        "max_iterations": get_aurai_config().max_iterations,
        "max_history": server_config.max_history,
        "provider": get_aurai_config().provider,
        "model": get_aurai_config().model,
    }


def main():
    """主入口函数"""
    global _conversation_history

    logger.info(f"启动 {server_config.name} MCP服务器")
    logger.info(f"AI提供商: {get_aurai_config().provider}")
    logger.info(f"模型: {get_aurai_config().model}")

    # 初始化对话历史持久化
    if server_config.enable_persistence:
        _conversation_history = _load_history_from_file()
        logger.info(f"持久化已启用,历史文件: {server_config.history_path}")
    else:
        logger.info("持久化未启用,使用内存模式")

    mcp.run()


if __name__ == "__main__":
    main()
