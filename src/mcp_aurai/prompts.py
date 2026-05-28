"""提示词模板模块"""

import json
from typing import Any


def _serialize_context(value: Any) -> str:
    """将上下文值序列化为适合放入提示词的文本。"""
    if isinstance(value, str):
        return value

    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        return str(value)


def _format_history_for_prompt(conversation_history: list[dict[str, Any]] | None, max_turns: int = 5) -> str:
    """将对话历史格式化为提示词可用的文本。

    按时间倒序取最近 max_turns 条非 summary 记录，summary 条目会作为前置上下文保留。
    """
    if not conversation_history:
        return ""

    # 分离 summary 和非 summary 条目
    summaries: list[str] = []
    turns: list[dict[str, Any]] = []

    for entry in conversation_history:
        if entry.get("type") == "summary":
            text = entry.get("summary_text", "")
            if text:
                summaries.append(text)
        else:
            turns.append(entry)

    parts: list[str] = []

    # 历史摘要放在最前面
    if summaries:
        parts.append("## 历史摘要\n")
        for s in summaries:
            parts.append(f"- {s}\n")

    # 最近 N 轮对话
    recent = turns[-max_turns:]
    if not recent:
        return "".join(parts)

    parts.append("## 对话历史\n\n")
    for i, turn in enumerate(recent, 1):
        turn_type = turn.get("type", "unknown")

        if turn_type == "consult":
            parts.append(f"### 第{i}轮 · 咨询\n")
            parts.append(f"- 问题类型: {turn.get('problem_type', 'unknown')}\n")
            parts.append(f"- 错误描述: {turn.get('error_message', '')}\n")
            if turn.get("had_answers"):
                parts.append("- 已补充回答\n")
            resp = turn.get("response", {})
            if resp.get("analysis"):
                parts.append(f"- 分析: {resp['analysis']}\n")
            if resp.get("guidance"):
                parts.append(f"- 建议: {resp['guidance']}\n")
            parts.append(f"- 已解决: {'是' if resp.get('resolved') else '否'}\n")

        elif turn_type == "progress":
            parts.append(f"### 第{i}轮 · 进度报告\n")
            parts.append(f"- 执行操作: {turn.get('actions_taken', '')}\n")
            parts.append(f"- 执行结果: {turn.get('result', '')}\n")
            if turn.get("new_error"):
                parts.append(f"- 新错误: {turn['new_error']}\n")
            if turn.get("feedback"):
                parts.append(f"- 反馈: {turn['feedback']}\n")
            resp = turn.get("response", {})
            if resp.get("guidance"):
                parts.append(f"- 顾问建议: {resp['guidance']}\n")
            parts.append(f"- 已解决: {'是' if resp.get('resolved') else '否'}\n")

        elif turn_type == "sync_context":
            files = turn.get("files", [])
            file_list = ", ".join(files[:5])
            if len(files) > 5:
                file_list += f" 等{len(files)}个文件"
            parts.append(f"### 第{i}轮 · 上下文同步\n")
            if file_list:
                parts.append(f"- 文件: {file_list}\n")
            if turn.get("project_info"):
                parts.append("- 已附带项目信息\n")

        else:
            parts.append(f"### 第{i}轮\n")
            parts.append(f"- {_serialize_context(turn)[:200]}\n")

        parts.append("\n")

    return "".join(parts)


def build_consult_prompt(
    problem_type: str,
    error_message: str,
    code_snippet: str | None = None,
    context: dict[str, Any] | None = None,
    attempts_made: str | None = None,
    iteration: int = 0,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """构建请求上级AI指导的提示词。格式说明由 SYSTEM_PROMPT 统一提供。"""
    context = context or {}

    context_desc = []
    if file_path := context.get("file_path"):
        context_desc.append(f"- 文件路径: {file_path}")
    if line_number := context.get("line_number"):
        context_desc.append(f"- 行号: {line_number}")
    if terminal_output := context.get("terminal_output"):
        context_desc.append(f"- 终端输出:\n```\n{terminal_output}\n```")
    if answers_to_questions := context.get("answers_to_questions"):
        context_desc.append(
            "- 对补充问题的回答:\n"
            f"```\n{_serialize_context(answers_to_questions)}\n```"
        )

    reserved_keys = {
        "file_path", "line_number", "terminal_output", "language", "answers_to_questions",
    }
    extra_context = {
        key: value for key, value in context.items()
        if key not in reserved_keys
    }
    if extra_context:
        context_desc.append(
            "- 其他上下文:\n"
            f"```json\n{_serialize_context(extra_context)}\n```"
        )

    history_desc = _format_history_for_prompt(conversation_history)

    prompt = f"""# 问题信息

- **问题类型**: {problem_type}
- **错误描述**: {error_message}
- **当前迭代**: 第 {iteration + 1} 轮

## 上下文
{chr(10).join(context_desc) if context_desc else "无"}

## 代码片段
{f"```{context.get('language', 'python')}\n{code_snippet}\n```" if code_snippet else "无"}

## 已尝试方案
{attempts_made if attempts_made else "无"}

{history_desc}
现在，请分析上述问题并给出你的指导。"""
    return prompt


def build_progress_prompt(
    iteration: int,
    actions_taken: str,
    result: str,
    new_error: str | None = None,
    feedback: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """构建报告进度的提示词。格式说明由 SYSTEM_PROMPT 统一提供。"""
    history_desc = _format_history_for_prompt(conversation_history)

    prompt = f"""# 进度报告

## 执行情况
- **迭代轮次**: 第 {iteration + 1} 轮
- **执行操作**: {actions_taken}
- **执行结果**: {result}
{f'- **新错误**: {new_error}' if new_error else ''}
{f'- **反馈**: {feedback}' if feedback else ''}

{history_desc}
请按照 SYSTEM_PROMPT 中定义的 JSON 格式回应，给出下一步指导。"""
    return prompt


# ---------------------------------------------------------------------------
# 响应 JSON Schema — 用于 OpenAI response_format 约束
# ---------------------------------------------------------------------------

CONSULT_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "consult_response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["aligning", "guiding"],
                    "description": "信息不足时用 aligning，信息充足时用 guiding",
                },
                "questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "需要补充信息时反问的问题列表",
                },
                "analysis": {
                    "type": ["string", "null"],
                    "description": "问题根因分析",
                },
                "guidance": {
                    "type": ["string", "null"],
                    "description": "具体可执行的指导建议",
                },
                "action_items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "分步执行计划",
                },
                "code_changes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string"},
                            "line": {"type": "number"},
                            "old": {"type": "string"},
                            "new": {"type": "string"},
                        },
                        "required": ["file", "old", "new"],
                        "additionalProperties": False,
                    },
                    "description": "具体的代码变更",
                },
                "verification": {
                    "type": ["string", "null"],
                    "description": "验证修复的方法",
                },
                "needs_another_iteration": {
                    "type": "boolean",
                    "description": "是否还需要继续迭代",
                },
                "resolved": {
                    "type": "boolean",
                    "description": "问题是否已完全解决",
                },
                "requires_human_intervention": {
                    "type": "boolean",
                    "description": "是否需要人工介入",
                },
            },
            "required": ["status", "questions", "analysis", "guidance", "action_items",
                         "code_changes", "verification", "needs_another_iteration",
                         "resolved", "requires_human_intervention"],
            "additionalProperties": False,
        },
    },
}


SYSTEM_PROMPT = """你是远程技术顾问，协助本地 AI 排查编程问题。

**重要约束**: 你无法直接访问本地文件系统。你看到的一切 — 代码、报错、项目结构 — 都来自本地 AI 通过两种方式提供:
- `sync_context`: 本地 AI 上传的完整文件内容和项目背景（以 "已上传文件" / "已同步项目背景" 形式出现）
- `consult_aurai`: 本地 AI 在问题描述中附带的信息（`error_message`、`code_snippet`、`context`）

**取舍**: 这些原则偏向严谨而非速度。对于 trivial 问题，用你自己的判断。

## 1. 只基于已有信息判断

**你看到什么就基于什么。不要猜你沒看到的东西。**

- 先检查已同步的文件中有没有相关代码。有 → 引用具体文件名。没有 → 反问要求上传。
- 本地 AI 没提供的文件路径、配置项、环境信息 → 不要假设它们存在。问。
- 如果问题的根因可能在你看不到的代码里 → 列出可疑方向，要求上传对应文件。
- 不要说 "检查你的 package.json" 如果 package.json 没有被同步 — 先让本地 AI 上传。

## 2. 信息不全不给方案

**不要猜。不要假设。缺信息就先问。**

- 没有具体错误信息 → 问。没有相关代码 → 要求 sync_context 上传。
- 如果问题有多种可能根因，列出它们 — 不要默默挑一个开始指导。
- 5W1H 缺口检查: What（什么现象）When（何时触发）Where（哪个文件）How（如何复现）
- 别给出基于 "可能是 X" 的猜测性方案。确认了再给。

## 3. 最小可执行指导

**基于已同步的代码给出具体修改。不画饼。不写教科书。**

- 你有文件内容 → 给具体 diff（old/new），文件路径用已同步文件名
- 你没有文件内容 → 说清楚改哪个文件的哪个逻辑，让本地 AI 去定位具体行号
- 不要建议安装新库/新工具，除非问题只能用它们解决
- 不要建议 "考虑重构" — 用户不是来听架构建议的

自问: "本地 AI 拿着我的指导能不能直接改代码？" 如果不能，重写。

## 4. 承认边界

**不知道就说不知道。解决不了就交给人。**

- 问题超出代码层面（硬件、网络、权限、第三方服务）→ requires_human_intervention=true
- 连续两轮同一方向没进展 → 换个思路，或设置 requires_human_intervention=true
- 不要编造不存在的 API、配置项、文件路径
- 不确定的结论前面加 "推测: "，不要当事实陈述
- 不确定某个文件是否存在 → 让本地 AI 确认，不要当作已知事实

## 5. 输出格式

按信息完整度选择一种 JSON 模式返回。两种模式字段完全一致，只是内容不同。

[模式 A: aligning — 信息不足，需要反问]
{
  "status": "aligning",
  "questions": ["具体问题1 — 说清楚要提供什么文件或信息", "具体问题2"],
  "analysis": null,
  "guidance": null,
  "action_items": [],
  "code_changes": [],
  "verification": null,
  "needs_another_iteration": false,
  "resolved": false,
  "requires_human_intervention": false
}

[模式 B: guiding — 信息充足，给出指导]
{
  "status": "guiding",
  "questions": [],
  "analysis": "根因分析 — 说清楚为什么会出这个问题",
  "guidance": "解决步骤 — 引用已同步文件名，指导改哪里怎么改",
  "action_items": ["步骤1：修改已同步的 X 文件中 Y 逻辑", "步骤2：让本地 AI 运行测试确认"],
  "code_changes": [
    {
      "file": "已同步的文件名（如 src/foo.py）",
      "line": 42,
      "old": "你看到的原代码（从已同步内容中摘取）",
      "new": "修改后的代码"
    }
  ],
  "verification": "如何确认修好了 — 基于项目已知的测试方式或通用验证逻辑",
  "needs_another_iteration": false,
  "resolved": false,
  "requires_human_intervention": false
}

**字段约束**:
- questions: 反问要具体 — "请上传 X 文件" 而不是 "请提供更多信息"
- code_changes.file: 只能用已同步的或本地 AI 明确提到的文件名，不要编造
- code_changes.old: 必须从已同步内容中一字不差摘取，不要臆造
- analysis: 2-4 句话说清根因
- guidance: 像 code review comment
- verification: 如果不知道项目的测试命令，描述验证逻辑让本地 AI 执行

---

**这些原则生效的标志**: 反问精准引用缺失信息、code_changes 中的 old 能在已同步内容中找到、指导不需要本地 AI 二次追问。"""
