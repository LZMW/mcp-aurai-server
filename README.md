# 上级顾问 MCP（Aurai Advisor）

> 让本地 AI 在遇到复杂编程问题时，向远程大模型继续请教的 MCP 服务。

当前仓库对应的是“可长期使用”的版本，已经补齐了这些关键能力：

- 多轮咨询与进度回报
- `sync_context` 文件同步
- 代码/配置文件自动转文本上传
- 会话隔离（`session_id`）
- 历史持久化、文件锁、原子写入
- 历史自动摘要
- 上下文窗口裁剪

---

## 适合做什么

这个 MCP 适合放在 Claude Code 或其他支持 stdio 方式的 MCP 客户端里使用。

典型场景：

- 本地 AI 已经尝试过，但问题还是没解开
- 需要把报错、代码、文档、配置一起交给“上级顾问”
- 希望让复杂排查变成“提问 -> 执行 -> 汇报 -> 下一步”的多轮流程

---

## 功能概览

- `consult_aurai`
  主要咨询工具。提交问题、代码片段、上下文、已尝试方案，获取上级顾问的分析和下一步建议。

- `sync_context`
  同步代码和文档上下文。
  现在不只支持 `.txt/.md`，还会自动把 `.py/.js/.ts/.json/.yaml/.toml/.ini` 等文本文件转成适合发送的文本内容。

- `report_progress`
  把执行结果回报给上级顾问，继续下一轮迭代。

- `get_status`
  查看当前会话状态、历史数量、模型与历史文件路径。

---

## 安装说明

更详细的安装步骤见：

- [Claude Code 安装指南](docs/CLAUDE_CODE_INSTALL.md)
- [用户手册](docs/用户手册.md)

这里先给一份最常用的安装流程。

### 1. 准备环境

```bash
# 需要 Python 3.10+
python --version

# 进入仓库目录
cd G:\codex\mcp-aurai-server
```

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv venv
venv\Scripts\activate
pip install -e ".[all-dev]"
```

### 3. 在 Claude Code 中注册 MCP

```bash
claude mcp add --scope user --transport stdio aurai-advisor ^
  --env AURAI_API_KEY="your-api-key" ^
  --env AURAI_BASE_URL="https://api.example.com/v1" ^
  --env AURAI_MODEL="gpt-4o" ^
  -- "G:\codex\mcp-aurai-server\venv\Scripts\python.exe" "-m" "mcp_aurai.server"
```

说明：

- `AURAI_BASE_URL` 必须是 OpenAI 兼容接口地址
- 当前版本只保留 `custom` 方式，不再使用旧的 `AURAI_PROVIDER`
- `--scope user` 表示在所有项目里都可用，最省心

### 4. 验证安装

```bash
claude mcp list
pytest
```

预期：

- `claude mcp list` 能看到 `aurai-advisor`
- `pytest` 通过

---

## 快速使用

### 场景 1：直接咨询问题

```python
consult_aurai(
    problem_type="runtime_error",
    error_message="启动时报 KeyError: api_key",
    code_snippet="config = load_config()\napi_key = config['api_key']",
    context={
        "file_path": "src/config.py",
        "terminal_output": "Traceback ...",
    }
)
```

### 场景 2：先上传代码文件，再咨询

```python
sync_context(
    operation="incremental",
    files=["src/main.py", "config/settings.json", "README.md"],
    project_info={
        "project_name": "My Project",
        "tech_stack": "Python + FastAPI"
    }
)

consult_aurai(
    problem_type="runtime_error",
    error_message="请结合已同步文件帮我排查启动失败"
)
```

注意：

- 不需要再手动把 `main.py` 复制成 `main.txt`
- 文本代码文件会自动转成文本发送
- 二进制文件会被跳过

### 场景 3：多问题并行，使用会话隔离

```python
consult_aurai(
    problem_type="runtime_error",
    error_message="问题 A",
    session_id="issue-a"
)

consult_aurai(
    problem_type="design_issue",
    error_message="问题 B",
    session_id="issue-b"
)
```

这能避免不同问题互相串台。

---

## sync_context 文件上传规则

### 会直接发送的

- `.md`、`.markdown`、`.mdx`
- `.txt`
- 各类代码与配置文本文件，例如：
  - `.py` `.js` `.ts` `.tsx`
  - `.json` `.yaml` `.yml` `.toml`
  - `.ini` `.cfg` `.env`
  - `.java` `.go` `.rs` `.cpp` `.cs`

### 会自动转换的

- 不是 `.txt/.md`，但内容是文本的文件
- 会自动生成一个 `.txt` 或 `.md` 的发送名
- 会在内容前附带“原始文件路径”和“自动转换后的发送名”

### 会跳过的

- 图片
- 压缩包
- 音视频
- 可执行文件
- 明显的二进制内容

如果一批文件里既有代码又有图片：

- 代码照常上传
- 图片会被记为 `skipped_files`
- 整次同步仍然成功

---

## 环境变量

### 必填

| 变量 | 说明 |
|------|------|
| `AURAI_API_KEY` | API 密钥 |
| `AURAI_BASE_URL` | OpenAI 兼容接口地址 |
| `AURAI_MODEL` | 模型名称 |

### 常用可选项

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AURAI_TEMPERATURE` | 温度 | `0.7` |
| `AURAI_MAX_ITERATIONS` | 最大迭代轮数 | `10` |
| `AURAI_MAX_HISTORY` | 每个会话保留的历史条数上限 | `50` |
| `AURAI_CONTEXT_WINDOW` | 总上下文窗口大小 | `200000` |
| `AURAI_MAX_MESSAGE_TOKENS` | 单条大文件消息大小上限 | `150000` |
| `AURAI_MAX_TOKENS` | 最大输出长度 | `32000` |
| `AURAI_LOG_LEVEL` | 日志级别 | `INFO` |
| `AURAI_ENABLE_PERSISTENCE` | 是否持久化历史 | `true` |
| `AURAI_HISTORY_PATH` | 默认会话历史文件路径 | `~/.mcp-aurai/history.json` |
| `AURAI_HISTORY_LOCK_TIMEOUT` | 历史文件锁等待时间（秒） | `10` |
| `AURAI_ENABLE_HISTORY_SUMMARY` | 是否启用历史摘要 | `true` |
| `AURAI_HISTORY_SUMMARY_KEEP_RECENT` | 摘要后保留的最近原始轮数 | `3` |
| `AURAI_HISTORY_SUMMARY_TRIGGER` | 触发摘要的原始记录阈值 | `8` |

---

## 当前版本的关键行为

### 1. 会话隔离

- 每个 `session_id` 都有各自的历史
- 默认不传时使用 `default`
- 不同会话会落到不同历史文件，避免串会话

### 2. 历史摘要

- 较早历史会自动压成一条“历史摘要”
- 最近几轮和最近一次 `sync_context` 会尽量保留原样
- 这样能减少上下文占用，给当前问题腾空间

### 3. 上下文窗口裁剪

- 会优先保留系统提示
- 优先保留最近一次 `sync_context`
- 再尽量保留最近历史轮次
- 必要时自动收缩本次输出长度，避免总窗口超限

### 4. 历史文件更稳

- 保存历史时使用锁文件避免并发写坏
- 写入采用临时文件再替换，避免留下半截 JSON

---

## 测试

```bash
pytest
```

当前主线覆盖的重点包括：

- 历史清空与持久化
- 会话隔离
- 自动文本转换上传
- 历史锁与原子写
- 历史摘要
- 上下文窗口裁剪

---

## 文档

- [Claude Code 安装指南](docs/CLAUDE_CODE_INSTALL.md)
- [用户手册](docs/用户手册.md)
- [开发文档](docs/开发文档.md)

---

## 常见问题

### 为什么上级顾问没收到我上传的代码文件？

旧版本要求先手动转成 `.txt`。当前版本已经支持自动转换文本文件。

如果还是没收到，优先检查：

- 文件路径是否存在
- 文件是不是二进制
- `sync_context` 返回里的 `uploaded_files` / `skipped_files`

### 为什么不同问题会互相影响？

如果你希望完全隔离，给不同问题传不同 `session_id`。

### 为什么历史文件看起来变短了？

这是历史摘要在工作。旧历史被压成纪要，不是丢了，而是换成更省上下文的“会议纪要”。
