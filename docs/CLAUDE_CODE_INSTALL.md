# Claude Code 安装指南

> **aurai-advisor MCP 服务器** - Claude Code 专用安装指南

---

## 📋 快速安装（5分钟）

### 1. 环境准备

```bash
# 检查 Python 版本（需要 3.10+）
python --version

# 检查 Claude Code
claude --version
```

### 2. 安装依赖（必须步骤！）

> **重要**：必须先创建虚拟环境并安装项目，否则 MCP 无法启动。

```bash
# 进入项目目录
cd D:\mcp-aurai-server

# 创建虚拟环境（如果还没有）
python -m venv venv

# 激活虚拟环境并安装项目
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# 以可编辑模式安装项目及其依赖
pip install -e ".[all-dev]"

# 验证安装
pytest tests/ -v
# 预期: 27 passed
```

### 3. 配置 MCP

> **关键**：使用 `--scope user` 确保在所有项目中都可用，避免每次切换目录都要重新安装。

**方式 A: 使用配置工具（推荐）**
```bash
python tools\control_center.py
```

1. 填写 API 密钥
2. 选择提供商和模型
3. 点击"生成配置文件"
4. **重要**：在生成的命令前添加 `--scope user`

**方式 B: 手动配置**

```bash
# 替换以下环境变量为你的实际值
claude mcp add --scope user --transport stdio aurai-advisor \
  --env AURAI_API_KEY="your-api-key" \
  --env AURAI_PROVIDER="custom" \
  --env AURAI_BASE_URL="https://www.chatgtp.cn/v1" \
  --env AURAI_MODEL="deepseek-v3-1-250821" \
  -- "D:\mcp-aurai-server\venv\Scripts\python.exe" "-m" "mcp_aurai.server"
```

### 4. 验证安装

```bash
# 检查 MCP 状态
claude mcp list

# 预期输出：
# aurai-advisor: ... - ✓ Connected

# 查看详细配置
claude mcp get aurai-advisor
# 应该显示：Scope: User config (available in all your projects)
```

### 5. 测试工具

在 Claude Code 对话中描述一个编程问题：

```
我遇到了一个 KeyError 问题，错误信息是 'api_key' not found
```

AI 会自动判断是否调用 `consult_aurai` 工具。

---

## 🔧 配置模板

### 智谱 AI（推荐新手）

```bash
claude mcp add --scope user --transport stdio aurai-advisor \
  --env AURAI_API_KEY="your-key" \
  --env AURAI_PROVIDER="zhipu" \
  --env AURAI_MODEL="glm-4-flash" \
  -- "D:\mcp-aurai-server\venv\Scripts\python.exe" "-m" "mcp_aurai.server"
```

### 自定义中转站

```bash
claude mcp add --scope user --transport stdio aurai-advisor \
  --env AURAI_API_KEY="your-key" \
  --env AURAI_PROVIDER="custom" \
  --env AURAI_BASE_URL="https://www.chatgtp.cn/v1" \
  --env AURAI_MODEL="deepseek-v3-1-250821" \
  -- "D:\mcp-aurai-server\venv\Scripts\python.exe" "-m" "mcp_aurai.server"
```

### OpenAI 官方

```bash
claude mcp add --scope user --transport stdio aurai-advisor \
  --env AURAI_API_KEY="sk-..." \
  --env AURAI_PROVIDER="openai" \
  --env AURAI_MODEL="gpt-4o" \
  -- "D:\mcp-aurai-server\venv\Scripts\python.exe" "-m" "mcp_aurai.server"
```

---

## 🐛 常见问题

### 每次打开 Claude Code 都要重新安装？

**原因**：使用了默认的本地范围（local），只在特定目录可用。

**解决方案**：使用 `--scope user` 重新安装：

```bash
# 1. 删除旧配置
claude mcp remove aurai-advisor -s local

# 2. 用 user scope 重新添加
claude mcp add --scope user ...
```

### MCP 工具没有出现

```bash
claude mcp list  # 检查配置
claude mcp remove aurai-advisor -s local
claude mcp add --scope user aurai-advisor ...  # 重新添加
```

### ModuleNotFoundError: No module named 'mcp_aurai'

**原因**：虚拟环境未创建或项目未安装。

**解决方案**：

```bash
cd D:\mcp-aurai-server
python -m venv venv
venv\Scripts\activate
pip install -e ".[all-dev]"
```

### Connection failed / Failed to connect

**可能原因**：
1. Python 路径不正确
2. 虚拟环境未正确安装

**排查步骤**：

```bash
# 1. 验证 Python 路径
D:\mcp-aurai-server\venv\Scripts\python.exe --version

# 2. 验证模块可导入
D:\mcp-aurai-server\venv\Scripts\python.exe -c "import mcp_aurai.server; print('OK')"

# 3. 查看详细配置
claude mcp get aurai-advisor
```

### 401 Unauthorized

- 检查 API 密钥是否正确
- 访问提供商平台重新生成

### 404 Model not found

- 使用配置工具的"刷新模型"功能
- 检查模型名称拼写

---

## 📚 相关文档

- [用户手册](用户手册.md) - 完整使用指南
- [开发文档](开发文档.md) - 技术细节

---

## 📞 获取 API 密钥

| 提供商 | 获取地址 |
|--------|----------|
| 智谱 AI | https://open.bigmodel.cn/usercenter/apikeys |
| OpenAI | https://platform.openai.com/api-keys |
| Anthropic | https://console.anthropic.com/settings/keys |
| Gemini | https://makersuite.google.com/app/apikey |

---

## 🔍 MCP 范围说明

Claude Code 支持 MCP 服务器的三种配置范围：

| 范围 | 命令参数 | 存储位置 | 可用性 | 推荐场景 |
|------|----------|----------|--------|----------|
| **本地** | `--scope local` (默认) | `~/.claude.json` 项目路径 | 仅当前项目目录 | ⚠️ 不推荐 |
| **项目** | `--scope project` | `.mcp.json` (项目根目录) | 团队共享 | 团队协作 |
| **用户** | `--scope user` | `~/.claude.json` 用户配置 | ✅ 所有项目 | ✅ 推荐 |

**推荐**：对于个人开发工具（如 aurai-advisor），使用 `--scope user` 确保在任何项目中都可用。

---

**完成！** 🎉 现在重启 Claude Code 后即可在所有项目中使用 aurai-advisor。
