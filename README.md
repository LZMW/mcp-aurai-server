# Aurai Advisor MCP

让本地 AI（Claude Code）在遇到复杂编程问题时，向远程大模型继续请教的 MCP 服务。

**工作原理**: 本地 AI 通过 `sync_context` 上传代码文件 → `consult_aurai` 提交问题 → 远程顾问返回分析 + 可执行步骤 → 本地 AI 用 `report_progress` 汇报进展 → 循环直到解决。

**关键约束**: 远程顾问**无法直接访问你的文件系统**。它只能看到你通过 `sync_context` 上传的文件内容和 `consult_aurai` 描述的信息。

---

## 安装

### 1. 环境要求

- Python 3.10+
- Claude Code（或其他支持 MCP stdio 的客户端）

### 2. 下载并安装依赖

```bash
git clone https://github.com/LZMW/mcp-aurai-server.git
cd mcp-aurai-server
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
pip install -e .
```

### 3. 在 Claude Code 中注册

```bash
claude mcp add --scope user --transport stdio aurai-advisor \
  --env AURAI_API_KEY="你的API密钥" \
  --env AURAI_BASE_URL="https://你的API地址/v1" \
  --env AURAI_MODEL="模型名称" \
  -- "完整路径\venv\Scripts\python.exe" "-m" "mcp_aurai.server"
```

**Windows 实际示例**:

```bash
claude mcp add --scope user --transport stdio aurai-advisor \
  --env AURAI_API_KEY="sk-xxxxxxxxxxxxxxxx" \
  --env AURAI_BASE_URL="https://api.openai.com/v1" \
  --env AURAI_MODEL="gpt-4o" \
  -- "D:\mcp-aurai-server\venv\Scripts\python.exe" "-m" "mcp_aurai.server"
```

`--scope user` 表示在所有项目中可用。

### 4. 验证

```bash
claude mcp list
```

看到 `aurai-advisor: ✓ Connected` 即成功。

### 5. 卸载

```bash
claude mcp remove "aurai-advisor" -s user
```

---

## 配置参数

所有参数通过环境变量设置，在 `claude mcp add` 时用 `--env` 传入。

### 必填

| 环境变量 | 说明 | 示例 |
|----------|------|------|
| `AURAI_API_KEY` | API 密钥 | `sk-xxxxxxxx` |
| `AURAI_BASE_URL` | OpenAI 兼容接口地址 | `https://api.openai.com/v1` |
| `AURAI_MODEL` | 模型名称 | `gpt-4o` / `claude-opus-4-1-20250805-thinking` |

### AI 调用控制

| 环境变量 | 默认值 | 范围 | 说明 |
|----------|--------|------|------|
| `AURAI_TEMPERATURE` | `0.7` | 0.0–2.0 | 生成温度。越低越确定，越高越随机 |
| `AURAI_MAX_TOKENS` | `32000` | ≥1 | 远程顾问单次回复的最大输出长度（tokens） |
| `AURAI_CONTEXT_WINDOW` | `200000` | ≥1 | 模型上下文窗口大小（tokens）。输入 + 输出的总上限 |
| `AURAI_MAX_MESSAGE_TOKENS` | `150000` | ≥1 | 单个文件超过此值会自动拆分成多段发送 |
| `AURAI_MAX_ITERATIONS` | `50` | 1–200 | 单个问题最多对话轮数。50 轮内解决 → 自动清空历史；超限 → 清空历史并返回 `requires_human_intervention` |

**上下文预算 & Token 监控**:

| 环境变量 | 默认值 | 范围 | 说明 |
|----------|--------|------|------|
| `AURAI_CONTEXT_HIGH_WATERMARK` | `0.85` | 0.5–1.0 | 上下文高水位线。输入 tokens 超过此比例时返回预警并主动压缩历史 |

每次 `consult_aurai` / `report_progress` 响应中均包含 `token_usage` 字段，实时展示输入 tokens、使用率、是否触发预警。当超过高水位线时，会主动压缩历史为输出腾空间。本地 AI 可根据 `warning=true` 提示调用 `sync_context(operation='clear')` 清空历史。

**上下文预算分配策略**: 优先保证 `AURAI_MAX_TOKENS` 的输出预算。输入过大时裁剪历史消息，不压缩输出。仅当基础消息（系统提示词 + 当前问题）本身就超过窗口时才缩减输出。

### 对话历史

| 环境变量 | 默认值 | 范围 | 说明 |
|----------|--------|------|------|
| `AURAI_MAX_HISTORY` | `50` | 1–200 | 每个会话在本地最多保留多少条历史记录 |
| `AURAI_PROMPT_HISTORY_TURNS` | `10` | 1–50 | 每次发送给远程顾问时附带最近多少轮原始对话（摘要不受此限制） |
| `AURAI_ENABLE_PERSISTENCE` | `true` | bool | 是否将历史保存到磁盘。关闭后重启 Claude Code 历史丢失 |
| `AURAI_HISTORY_PATH` | `~/.mcp-aurai/history.json` | — | 历史文件存储路径 |
| `AURAI_HISTORY_LOCK_TIMEOUT` | `10` | 1–120s | 跨进程文件锁等待超时 |
| `AURAI_ENABLE_HISTORY_SUMMARY` | `true` | bool | 是否启用历史摘要。仅在接近 max_history（80%）时触发，保留 60% 原始记录 |

**历史机制说明**:

- `AURAI_MAX_HISTORY`（50 条）是本地存储上限——现代 200K 上下文下纯对话远填不满，真正的瓶颈是 `sync_context` 上传的大文件
- 摘要不再按固定条数触发，而是在接近 max_history 时（40/50 条）才启动
- Token 水位线预警（`AURAI_CONTEXT_HIGH_WATERMARK`）是实时防线，在每次请求前检查
- 不同 `session_id` 的历史互相隔离

### 进程管理

| 环境变量 | 默认值 | 范围 | 说明 |
|----------|--------|------|------|
| `AURAI_STDIO_IDLE_TIMEOUT_SECONDS` | `600` | 0–86400 | 空闲多久后自动退出。`0` = 永不退出（推荐） |
| `AURAI_STDIO_IDLE_CHECK_INTERVAL_SECONDS` | `30` | 1–3600 | 空闲检查间隔 |

**推荐设置 `AURAI_STDIO_IDLE_TIMEOUT_SECONDS=0`**，避免 Claude Code 还在运行但 MCP 因空闲被误杀。空闲退出前会检查父进程是否存活，但如果不在意残留进程，直接禁用最省心。

### 其他

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `AURAI_LOG_LEVEL` | `INFO` | 日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR`。调试时建议 `DEBUG` |

---

## 使用指南

MCP 注册后，Claude Code 中自动出现 4 个工具：

### 典型调用流程

```
1. sync_context(operation='sync', files=['src/bug.py'], project_info={...})
   ↑ 让顾问看到你的代码

2. consult_aurai(problem_type='runtime_error', error_message='...')
   ↑ 提交问题，获取分析

3. 如返回 status='need_info' → 搜集顾问反问的信息 → 再次 consult_aurai(answers_to_questions='...')
   ↑ 多轮对齐

4. 如返回 status='success' → 按 action_items 执行修改

5. report_progress(actions_taken='改了X', result='success')
   ↑ 汇报进展，获取下一步指导

6. 重复 4-5，直到 resolved=true
```

### 工具速查

| 工具 | 用途 |
|------|------|
| `sync_context` | 上传文件和项目背景。`operation='sync'` 追加，`'clear'` 清空 |
| `consult_aurai` | 提交问题。支持多轮：收到反问→搜集信息→`answers_to_questions` 继续 |
| `report_progress` | 按顾问指导执行后汇报结果，获取下一步 |
| `get_status` | 查看会话状态（历史条数、模型、空闲时间） |

### 会话隔离

不同任务传不同的 `session_id`，避免上下文串扰：

```
consult_aurai(session_id='bug-123', ...)   # 修 Bug A
consult_aurai(session_id='feature-456', ...) # 写功能 B
```

---

## 常见问题

### 上级顾问收不到我上传的代码？

检查 `sync_context` 返回的 `uploaded_files` 和 `skipped_files`。二进制文件（图片、压缩包）会被自动跳过。代码文件（.py/.js/.ts 等）会自动转换为文本发送。

### 不同问题互相干扰？

给不同问题传不同的 `session_id`。或设置 `is_new_question=true` 清空当前会话历史。

### Claude Code 提示 MCP 连不上？

- 检查 `claude mcp list` 确认状态
- 查看 `AURAI_STDIO_IDLE_TIMEOUT_SECONDS`，推荐设为 `0` 禁用空闲退出
- 查看日志：`AURAI_LOG_LEVEL=DEBUG` 可看到详细日志（输出到 stderr）

### 历史文件变得很大？

历史摘要在自动工作。旧记录被压缩为纪要而非删除，可设置 `AURAI_ENABLE_HISTORY_SUMMARY=false` 完全禁用摘要（不推荐）。

### 怎么切换模型？

```bash
claude mcp remove "aurai-advisor" -s user
claude mcp add --scope user --transport stdio aurai-advisor \
  --env AURAI_API_KEY="sk-..." \
  --env AURAI_BASE_URL="https://api.openai.com/v1" \
  --env AURAI_MODEL="新模型名称" \
  -- "D:\mcp-aurai-server\venv\Scripts\python.exe" "-m" "mcp_aurai.server"
```
