# Claude Code 安装指南

> 这份文档对应当前仓库主线，适用于 Claude Code 中安装 `aurai-advisor`。

---

## 安装前准备

需要先确认两件事：

1. 你的机器能运行 `Python 3.10+`
2. 你已经安装并能使用 `Claude Code`

检查命令：

```bash
python --version
claude --version
```

---

## 一步一步安装

### 1. 进入项目目录

```bash
cd G:\codex\mcp-aurai-server
```

### 2. 创建虚拟环境

```bash
python -m venv venv
```

### 3. 激活虚拟环境

Windows：

```bash
venv\Scripts\activate
```

macOS / Linux：

```bash
source venv/bin/activate
```

### 4. 安装项目

```bash
pip install -e ".[all-dev]"
```

### 5. 注册到 Claude Code

最推荐用 `--scope user`，这样所有项目里都能直接用，不用切目录后反复重装。

```bash
claude mcp add --scope user --transport stdio aurai-advisor ^
  --env AURAI_API_KEY="your-api-key" ^
  --env AURAI_BASE_URL="https://api.example.com/v1" ^
  --env AURAI_MODEL="gpt-4o" ^
  -- "G:\codex\mcp-aurai-server\venv\Scripts\python.exe" "-m" "mcp_aurai.server"
```

如果你用的是智谱：

```bash
claude mcp add --scope user --transport stdio aurai-advisor ^
  --env AURAI_API_KEY="your-api-key" ^
  --env AURAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4/" ^
  --env AURAI_MODEL="glm-4.7" ^
  -- "G:\codex\mcp-aurai-server\venv\Scripts\python.exe" "-m" "mcp_aurai.server"
```

如果你用的是 DeepSeek：

```bash
claude mcp add --scope user --transport stdio aurai-advisor ^
  --env AURAI_API_KEY="your-api-key" ^
  --env AURAI_BASE_URL="https://api.deepseek.com/v1" ^
  --env AURAI_MODEL="deepseek-chat" ^
  -- "G:\codex\mcp-aurai-server\venv\Scripts\python.exe" "-m" "mcp_aurai.server"
```

---

## 验证安装

### 1. 检查 Claude Code 里的 MCP 状态

```bash
claude mcp list
```

应该能看到 `aurai-advisor`。

### 2. 运行测试

```bash
pytest
```

### 3. 实际对话验证

在 Claude Code 里随便问一个稍复杂的编程问题，例如：

```text
我项目启动时报错，请帮我排查
```

如果客户端开始调用 `consult_aurai` 或 `sync_context`，说明接通了。

---

## 推荐的环境变量

最少只需要这 3 个：

- `AURAI_API_KEY`
- `AURAI_BASE_URL`
- `AURAI_MODEL`

如果你想更稳一些，建议顺手补这几个：

```bash
--env AURAI_MAX_ITERATIONS="10" ^
--env AURAI_LOG_LEVEL="INFO" ^
--env AURAI_CONTEXT_WINDOW="200000" ^
--env AURAI_MAX_MESSAGE_TOKENS="150000" ^
--env AURAI_MAX_TOKENS="32000"
```

如果你想让不同项目互不影响，也可以给不同安装项配不同的历史文件路径：

```bash
--env AURAI_HISTORY_PATH="G:\codex\mcp-aurai-server\.mcp-aurai\history.json"
```

---

## 你现在会得到什么能力

安装完成后，这个 MCP 已经支持：

- 多轮咨询与进度回报
- `session_id` 会话隔离
- 历史自动摘要
- 历史文件锁与原子写
- 自动把代码/配置文件转成文本上传给上级顾问

这意味着：

- 不需要再手动把 `main.py` 改名成 `main.txt`
- 不同问题可以各自走各自的上下文
- 长会话不会越来越臃肿

---

## 常见问题

### 1. `claude mcp list` 里看不到它

先删掉旧配置，再重新加：

```bash
claude mcp remove aurai-advisor -s user
claude mcp add --scope user ...
```

### 2. 报 `ModuleNotFoundError`

说明虚拟环境没装好，重新执行：

```bash
cd G:\codex\mcp-aurai-server
python -m venv venv
venv\Scripts\activate
pip install -e ".[all-dev]"
```

### 3. 代码文件上传了，但上级顾问没看到

先看 `sync_context` 返回结果里的：

- `uploaded_files`
- `auto_converted_files`
- `skipped_files`

如果文件在 `skipped_files` 里，通常是：

- 路径不存在
- 文件是二进制
- 文件内容无法按文本读取

### 4. 为什么旧问题会影响新问题

给不同问题传不同 `session_id`，或者开始新问题时设置 `is_new_question=true`。

---

## 推荐阅读

- [README](../README.md)
- [用户手册](用户手册.md)
- [开发文档](开发文档.md)
