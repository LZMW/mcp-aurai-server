"""提示词模板模块"""

from typing import Any


def build_consult_prompt(
    problem_type: str,
    error_message: str,
    code_snippet: str | None = None,
    context: dict[str, Any] | None = None,
    attempts_made: str | None = None,
    iteration: int = 0,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """
    构建请求上级AI指导的提示词

    Args:
        problem_type: 问题类型
        error_message: 错误描述
        code_snippet: 相关代码片段
        context: 上下文信息
        attempts_made: 已尝试的解决方案
        iteration: 当前迭代次数
        conversation_history: 对话历史
    """
    context = context or {}

    # 构建上下文描述
    context_desc = []
    if file_path := context.get("file_path"):
        context_desc.append(f"- 文件路径: {file_path}")
    if line_number := context.get("line_number"):
        context_desc.append(f"- 行号: {line_number}")
    if terminal_output := context.get("terminal_output"):
        context_desc.append(f"- 终端输出:\n```\n{terminal_output}\n```")

    # 构建对话历史
    history_desc = ""
    if conversation_history:
        history_desc = "\n## 对话历史\n\n"
        for i, turn in enumerate(conversation_history[-5:], 1):  # 只保留最近5轮
            history_desc += f"### 第{i}轮\n"
            if "action" in turn:
                history_desc += f"**执行操作**: {turn['action']}\n"
            if "result" in turn:
                history_desc += f"**执行结果**: {turn['result']}\n"
            history_desc += "\n"

    prompt = f"""# 你是上级AI顾问

## 角色
你是一位经验丰富的技术顾问，正在指导一位"本地AI助手"解决编程问题。

## 任务
分析以下问题，提供清晰、可执行的指导。

## 问题信息
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

## 你的回应格式

**重要**: 首先评估信息完整度，然后选择对应的模式返回。

**信息不足时（缺少具体错误、代码、上下文）**:
```json
{{
  "status": "aligning",
  "questions": ["需补充的问题1", "需补充的问题2"],
  "analysis": null,
  "guidance": null
}}
```

**信息充足时**:
```json
{{
  "status": "guiding",
  "questions": [],
  "analysis": "问题分析 - 简明扼要分析问题根源",
  "guidance": "指导建议 - 具体建议的文字描述",
  "action_items": ["步骤1", "步骤2", "..."],
  "code_changes": [
    {{
      "file": "文件路径",
      "line": 行号,
      "old": "原代码",
      "new": "新代码"
    }}
  ],
  "verification": "验证方法",
  "needs_another_iteration": false,
  "resolved": false,
  "requires_human_intervention": false
}}
```

## 字段说明

- **status**: 必须是 "aligning"（信息不足）或 "guiding"（信息充足）
- **questions**: 反问列表（仅在 aligning 模式）
- **analysis**: 分析问题根本原因
- **guidance**: 给出具体、可执行的指导建议
- **action_items**: 数组，列出具体的执行步骤
- **code_changes**: 数组（可选），如果需要修改代码，列出具体的代码变更
- **verification**: 验证方法（新增）
- **needs_another_iteration**: 布尔值，是否需要继续迭代
- **resolved**: 布尔值，问题是否已解决
- **requires_human_intervention**: 布尔值，是否需要人工介入

## 重要原则

1. **指导要具体、可执行** - 避免模糊建议
2. **最小改动原则** - 优先考虑最小改动来解决问题
3. **分步骤指导** - 如果问题复杂，分步骤给出建议
4. **承认限制** - 承认无法解决的问题，及时设置 requires_human_intervention=true
5. **避免无限循环** - 如果连续多次建议相同方向，考虑人工介入

现在，请分析上述问题并给出你的指导。
"""
    return prompt


def build_progress_prompt(
    iteration: int,
    actions_taken: str,
    result: str,
    new_error: str | None = None,
    feedback: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """
    构建报告进度的提示词

    Args:
        iteration: 迭代次数
        actions_taken: 已执行的行动
        result: 执行结果 (success | failed | partial)
        new_error: 新的错误信息
        feedback: 执行反馈
        conversation_history: 对话历史
    """
    # 构建对话历史
    history_desc = ""
    if conversation_history:
        history_desc = "\n## 对话历史\n\n"
        for i, turn in enumerate(conversation_history[-5:], 1):
            history_desc += f"### 第{i}轮\n"
            if "action" in turn:
                history_desc += f"**执行操作**: {turn['action']}\n"
            if "result" in turn:
                history_desc += f"**执行结果**: {turn['result']}\n"
            history_desc += "\n"

    prompt = f"""# 进度报告

## 执行情况
- **迭代轮次**: 第 {iteration + 1} 轮
- **执行操作**: {actions_taken}
- **执行结果**: {result}
{f'- **新错误**: {new_error}' if new_error else ''}
{f'- **反馈**: {feedback}' if feedback else ''}
{history_desc}

## 请判断

1. 问题是否已解决？
2. 是否需要继续尝试其他方案？
3. 是否需要人工介入？

请按照之前的JSON格式回应，给出下一步指导。
"""
    return prompt


SYSTEM_PROMPT = """你是一位严谨的**首席技术架构师**。

**交互原则**:
1. **拒绝盲目指导**: 信息不足时严禁给出方案，必须先反问。
2. **颗粒度对齐**: 评估信息是否满足 5W1H（What何事、When何时、Where何地、Who何人、Why为何、How如何）。

**输出模式**:
请根据信息完整度选择一种模式返回 JSON：

[模式 A: 对齐阶段 (Alignment Phase)]
(当信息模糊、缺代码、缺报错、缺上下文时)
{
  "status": "aligning",
  "questions": ["需补充的关键问题1", "需补充的关键问题2"],
  "analysis": null,
  "guidance": null
}

[模式 B: 指导阶段 (Guidance Phase)]
(当信息充足时)
{
  "status": "guiding",
  "questions": [],
  "analysis": "根因分析",
  "guidance": "具体步骤",
  "action_items": ["步骤1", "步骤2"],
  "code_changes": [
    {
      "file": "文件路径",
      "line": 行号,
      "old": "原代码",
      "new": "新代码"
    }
  ],
  "verification": "验证方法",
  "needs_another_iteration": false,
  "resolved": false,
  "requires_human_intervention": false
}

**信息评估标准**:
- 必须有: 具体的错误信息/现象描述
- 应该有: 相关代码片段
- 推荐有: 已尝试的解决方案、执行环境、堆栈信息
"""
