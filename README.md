# 上级顾问 MCP (Aurai Advisor)

> 让本地 AI 获取远程 AI 指导的 MCP 服务器

**版本**: v2.1.1 (工具引导增强版)
**状态**: [OK] 生产就绪
**测试**: 27/27 通过

---

## 功能特点

- [OK] **多轮对话机制** - 智能追问，逐步解决问题
- [OK] **智能对话管理** - 自动检测新问题并清空历史，确保干净的上下文
- [OK] **智能工具引导** - 工具描述中包含相关工具推荐，提升使用效率 ⭐ 新增
- [OK] **5种 AI 提供商** - zhipu, openai, anthropic, gemini, custom
- [OK] **动态模型获取** - 实时获取最新可用模型
- [OK] **对话历史持久化** - 自动保存到用户目录
- [OK] **GUI 配置工具** - 可视化配置生成
- [OK] **完整测试覆盖** - 100% 通过率

---

## 快速开始

### 1. 安装

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
# 预期: ========== 27 passed ==========
```

### 2. 配置

**方式 A: 使用配置工具（推荐）**
```bash
python tools\control_center.py
```

**方式 B: 手动配置**
```bash
claude mcp add aurai-advisor \
  -e AURAI_API_KEY="your-api-key" \
  -e AURAI_PROVIDER="custom" \
  -e AURAI_BASE_URL="https://www.chatgtp.cn/v1" \
  -e AURAI_MODEL="deepseek-v3-1-250821" \
  -- "C:\Users\29493\Desktop\mcp-aurai-server\venv\Scripts\python.exe" -m mcp_aurai.server
```

### 3. 使用

重启 Claude Code 后，在对话中直接描述编程问题：

```
我遇到了一个 KeyError 问题，错误信息是 'api_key' not found
相关代码如下：
[粘贴代码]
```

AI 会自动判断是否调用 `consult_aurai` 工具。

---

## MCP 工具

### consult_aurai（主要工具）
请求上级 AI 指导解决编程问题

**参数**:
- `problem_type`: 问题类型（runtime_error/syntax_error/design_issue/other）
- `error_message`: 错误描述
- `code_snippet`: 代码片段（可选）
- `context`: 上下文信息（可选）
- `is_new_question`: 是否为新问题（可选，默认false）- 设置为true会清空之前的对话历史

**返回**: 上级 AI 的分析和建议

**对话历史管理**:
- **自动清空**: 当上级AI返回 `resolved=true` 时，自动清空对话历史
- **手动清空**: 设置 `is_new_question=true` 强制清空历史，开始新对话
- **历史限制**: 最多保存50条历史记录（可通过 `AURAI_MAX_HISTORY` 配置）

### sync_context
同步代码上下文

**参数**:
- `operation`: 操作类型（full_sync/incremental/clear）
- `files`: 文件路径列表（可选）

### report_progress
报告执行进度

**参数**:
- `actions_taken`: 已执行的行动
- `result`: 执行结果（success/failed/partial）

### get_status
获取当前状态

**返回**: 对话历史数量、状态信息

---

## 文档

| 文档 | 说明 |
|------|------|
| [用户手册](docs/用户手册.md) | 完整使用指南 |
| [安装指南](docs/CLAUDE_CODE_INSTALL.md) | Claude Code 专用安装 |
| [开发文档](docs/开发文档.md) | 技术细节和架构 |

---

## 支持的 AI 提供商

| 提供商 | 说明 | 获取 API 密钥 | 推荐模型 |
|--------|------|--------------|----------|
| **zhipu** | 智谱 AI | https://open.bigmodel.cn/ | glm-4-flash |
| **openai** | OpenAI 官方 | https://platform.openai.com/api-keys | gpt-4o |
| **anthropic** | Claude | https://console.anthropic.com/ | claude-3-5-sonnet-20241022 |
| **gemini** | Google Gemini | https://makersuite.google.com/app/apikey | gemini-1.5-flash |
| **custom** | 自定义中转站 | 第三方提供商 | deepseek-v3-1-250821 |

---

## 配置工具

```bash
python tools\control_center.py
```

**功能**:
- 生成配置文件（包含完整安装指导）
- 查看对话历史
- 从 API 动态获取模型列表
- 5 种快速配置预设

---

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_server.py -v
pytest tests/test_llm.py -v
pytest tests/test_config.py -v

# 查看测试覆盖率
pytest tests/ --cov=src/mcp_aurai --cov-report=html
```

---

## 项目结构

```
mcp-aurai-server/
├── src/mcp_aurai/          # MCP Server 源代码
│   ├── server.py           # 主服务器（4个工具）
│   ├── config.py           # 配置管理
│   ├── llm.py              # AI客户端（5种提供商）
│   └── prompts.py          # 提示词模板
│
├── tools/
│   └── control_center.py   # GUI 配置工具 v2.0
│
├── tests/                  # 27个测试用例
│   ├── test_server.py
│   ├── test_llm.py
│   └── test_config.py
│
├── docs/                   # 文档
│   ├── 用户手册.md
│   ├── CLAUDE_CODE_INSTALL.md
│   └── 开发文档.md
│
├── README.md               # 本文件
├── pyproject.toml          # 项目配置
├── pytest.ini              # 测试配置
└── .env.example            # 环境变量示例
```

---

## 环境变量

```bash
# 必填
AURAI_API_KEY=sk-xxx                    # API 密钥
AURAI_PROVIDER=custom                   # 提供商
AURAI_BASE_URL=https://www.chatgtp.cn/v1  # API 地址（custom必填）
AURAI_MODEL=deepseek-v3-1-250821        # 模型名称

# 可选
AURAI_MAX_ITERATIONS=10                 # 最大迭代次数（默认10）
AURAI_MAX_HISTORY=50                    # 对话历史最大保存数（默认50）
AURAI_TEMPERATURE=1.0                   # 温度参数（默认1.0）
AURAI_MAX_TOKENS=100000                 # 最大tokens（默认100000）

# 自动管理（无需设置）
AURAI_ENABLE_PERSISTENCE=true           # 对话历史持久化
AURAI_HISTORY_PATH=~/.mcp-aurai/history.json  # 历史文件路径
AURAI_LOG_LEVEL=INFO                    # 日志级别
```

---

## 故障排查

### MCP 工具没有出现
```bash
claude mcp list                          # 检查配置
claude mcp remove aurai-advisor -s local # 删除旧配置
claude mcp add aurai-advisor ...         # 重新添加
```

### ModuleNotFoundError
```bash
pip install -e .                         # 重新安装
```

### 401 Unauthorized
- 检查 API 密钥是否正确
- 访问提供商平台重新生成密钥

### 404 Model not found
- 使用配置工具的"刷新模型"功能
- 检查模型名称拼写

---

## 获取帮助

- **用户手册**: [docs/用户手册.md](docs/用户手册.md)
- **安装指南**: [docs/CLAUDE_CODE_INSTALL.md](docs/CLAUDE_CODE_INSTALL.md)
- **开发文档**: [docs/开发文档.md](docs/开发文档.md)
- **更新日志**: [CHANGELOG_v2.1.md](CHANGELOG_v2.1.md)
- **论坛更新简报**: [论坛更新简报_v2.1.1](docs/论坛更新简报_v2.1.1_工具引导增强.md)

---

## 许可证

MIT License

---

**项目名称**: mcp-aurai-server
**版本**: v2.1.1
**状态**: [OK] 生产就绪
