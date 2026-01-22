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

### 2. 安装依赖

```bash
# 进入项目目录
cd mcp-aurai-server

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -e ".[all-dev]"

# 验证安装
pytest tests/ -v
# 预期: 27 passed
```

### 3. 配置 MCP

**方式 A: 使用配置工具（推荐）**
```bash
python tools\control_center.py
```

1. 填写 API 密钥
2. 选择提供商和模型
3. 点击"生成配置文件"
4. 复制生成的命令并执行

**方式 B: 手动配置**
```bash
claude mcp add aurai-advisor \
  -e AURAI_API_KEY="your-api-key" \
  -e AURAI_PROVIDER="custom" \
  -e AURAI_BASE_URL="https://www.chatgtp.cn/v1" \
  -e AURAI_MODEL="deepseek-v3-1-250821" \
  -- "C:\Users\29493\Desktop\mcp-aurai-server\venv\Scripts\python.exe" -m mcp_aurai.server
```

### 4. 验证安装

```bash
# 检查 MCP 状态
claude mcp list

# 预期输出：
# aurai-advisor: ... - ✓ Connected
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
claude mcp add aurai-advisor \
  -e AURAI_API_KEY="your-key" \
  -e AURAI_PROVIDER="zhipu" \
  -e AURAI_MODEL="glm-4-flash" \
  -- "C:\Users\29493\Desktop\mcp-aurai-server\venv\Scripts\python.exe" -m mcp_aurai.server
```

### 自定义中转站
```bash
claude mcp add aurai-advisor \
  -e AURAI_API_KEY="your-key" \
  -e AURAI_PROVIDER="custom" \
  -e AURAI_BASE_URL="https://www.chatgtp.cn/v1" \
  -e AURAI_MODEL="deepseek-v3-1-250821" \
  -- "C:\Users\29493\Desktop\mcp-aurai-server\venv\Scripts\python.exe" -m mcp_aurai.server
```

### OpenAI 官方
```bash
claude mcp add aurai-advisor \
  -e AURAI_API_KEY="sk-..." \
  -e AURAI_PROVIDER="openai" \
  -e AURAI_MODEL="gpt-4o" \
  -- "C:\Users\29493\Desktop\mcp-aurai-server\venv\Scripts\python.exe" -m mcp_aurai.server
```

---

## 🐛 常见问题

### MCP 工具没有出现
```bash
claude mcp list  # 检查配置
claude mcp remove aurai-advisor -s local
claude mcp add aurai-advisor ...  # 重新添加
```

### ModuleNotFoundError
```bash
pip install -e .  # 重新安装
```

### 401 Unauthorized
- 检查 API 密钥是否正确
- 访问提供商平台重新生成

### 404 Model not found
- 使用配置工具的"刷新模型"功能
- 检查模型名称

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

**完成！** 🎉 重启 Claude Code 后即可使用。
