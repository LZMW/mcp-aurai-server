# 上级顾问 MCP (Aurai Advisor)

> 让本地 AI 获取远程 AI 指导的 MCP 服务器

**版本**: v2.2.0 (重构与文件上传修复)
**状态**: [OK] 生产就绪
**发布日期**: 2026-01-24
**优化模型**: GLM-4.7 (智谱 AI)

---

## 功能特点

- [OK] **多轮对话机制** - 智能追问，逐步解决问题
- [OK] **智能对话管理** - 自动检测新问题并清空历史，确保干净的上下文
- [OK] **智能工具引导** - 工具描述中包含相关工具推荐
- [OK] **文件上传支持** ⭐ - 支持通过 `sync_context` 上传文件，大文件自动分批发送
- [OK] **GLM-4.7 优化** - 基于 GLM-4.7 模型参数硬编码优化（200K 上下文）
- [OK] **对话历史持久化** - 自动保存到用户目录
- [OK] **GUI 配置工具** - 可视化配置生成

---

## v2.2.0 更新说明

### ⚠️ 重要：旧版用户迁移指南

如果您已经安装了 **v2.1.x 或更早版本**，请注意以下迁移事项：

#### 情况 1：使用 `custom` provider（OpenAI 兼容 API）的用户 ✅

**好消息**：无需重新安装或重新配置！

```bash
# 只需升级版本即可
cd D:\mcp-aurai-server
git pull origin main
pip install -e ".[all-dev]"

# 重启 Claude Code，自动生效
```

- ✅ 新的环境变量（`AURAI_CONTEXT_WINDOW`、`AURAI_MAX_MESSAGE_TOKENS`、`AURAI_MAX_TOKENS`）是**可选的**
- ✅ 默认值已针对 GLM-4.7 优化（200K 上下文）
- ✅ 文件上传修复是透明的，会自动生效

#### 情况 2：使用 `zhipu`、`openai`、`anthropic`、`gemini` provider 的用户 ❌

**需要迁移**：v2.2.0 移除了这些 provider，需要切换到 `custom` + OpenAI 兼容 API。

**迁移步骤（以智谱 AI 为例）**：

```bash
# 1. 删除旧配置
claude mcp remove aurai-advisor -s user

# 2. 重新添加（使用 custom provider）
claude mcp add --scope user --transport stdio aurai-advisor \
  --env AURAI_API_KEY="your-api-key" \
  --env AURAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4/" \
  --env AURAI_MODEL="glm-4.7" \
  -- "D:\mcp-aurai-server\venv\Scripts\python.exe" "-m" "mcp_aurai.server"

# 3. 重启 Claude Code
```

**各服务商迁移配置**：

| 原提供商 | 新 AURAI_BASE_URL | 推荐模型 |
|---------|------------------|---------|
| `zhipu` | `https://open.bigmodel.cn/api/paas/v4/` | `glm-4.7` |
| `openai` | `https://api.openai.com/v1` | `gpt-4o` |
| `anthropic` | 需使用第三方兼容 API | - |
| `gemini` | 需使用第三方兼容 API | - |

> **提示**：升级后，建议运行 `python .ai_temp/test_file_upload_fix.py` 验证文件上传功能是否正常。

---

### 重大变更

1. **简化服务商支持**
   - ✅ 只保留 `custom` provider（OpenAI 兼容 API）
   - ❌ 移除 zhipu、openai、anthropic、gemini 直接支持
   - ✅ 所有兼容 OpenAI API 的服务均可使用

2. **文件上传功能修复** ⭐
   - ✅ 修复 `sync_context` 文件内容未发送给上级 AI 的问题
   - ✅ 大文件自动分批发送（超过 `max_message_tokens` 时）
   - ✅ 动态 Token 估算，根据配置自动调整

3. **GLM-4.7 模型优化** 🎯
   - ✅ 基于 GLM-4.7 模型参数设置默认值
   - ✅ 上下文窗口：200,000 tokens（默认）
   - ✅ 单条消息上限：150,000 tokens（默认）
   - ✅ 最大输出：32,000 tokens（默认）
   - ✅ 支持通过环境变量覆盖（适用于其他模型）

---

## GLM-4.7 Token 配置说明

本版本采用 **GLM-4.7** 模型参数作为默认值，同时支持通过环境变量覆盖（适用于其他模型）：

| 配置项 | 默认值 | 环境变量 | 说明 |
|--------|-------|----------|------|
| `context_window` | 200,000 | `AURAI_CONTEXT_WINDOW` | GLM-4.7 上下文窗口上限 |
| `max_message_tokens` | 150,000 | `AURAI_MAX_MESSAGE_TOKENS` | 单条文件消息上限 |
| `max_tokens` | 32,000 | `AURAI_MAX_TOKENS` | 上级 AI 最大输出长度 |

**Token 分配策略**：
```
200K (总上下文)
├── 32K (输出) - 上级 AI 的分析回复
└── 168K (输入)
    ├── ~18K (系统 + 历史 + 问题)
    ├── 150K (最大单条文件)
    └── ~ - 安全边际
```

**容量参考**：
- 单文件上传上限：~15-20 万中文字符
- 上级 AI 输出上限：~2-3 万中文字符
- 对话历史：约 10-15 轮完整对话

> **注意**：默认值基于 GLM-4.7 优化，使用其他模型时可通过环境变量调整。

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
python .ai_temp/test_file_upload_fix.py
# 预期: ✅ 所有测试通过！
```

### 2. 配置

**重要**: 使用 `--scope user` 确保在所有项目中都可用。

```bash
claude mcp add --scope user --transport stdio aurai-advisor \
  --env AURAI_API_KEY="your-api-key" \
  --env AURAI_BASE_URL="https://api.example.com/v1" \
  --env AURAI_MODEL="gpt-4o" \
  -- "D:\mcp-aurai-server\venv\Scripts\python.exe" "-m" "mcp_aurai.server"
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
- `is_new_question`: 是否为新问题（可选，默认false）

**返回**: 上级 AI 的分析和建议

**🔗 相关工具**:
- **sync_context**：上传文档或代码文件（支持 .md 和 .txt）
- **report_progress**：报告执行进度并获取下一步指导
- **get_status**：查看当前对话状态、配置信息

**对话历史管理**:
- **自动清空**: 当上级AI返回 `resolved=true` 时，自动清空对话历史
- **手动清空**: 设置 `is_new_question=true` 强制清空历史
- **历史限制**: 最多保存50条历史记录

### sync_context ⭐
同步代码上下文，上传文件供上级 AI 阅读

**参数**:
- `operation`: 操作类型（full_sync/incremental/clear）
- `files`: 文件路径列表（支持 .txt 和 .md）
- `project_info`: 项目信息字典（可选）

**功能特性**:
- 📄 支持上传 Markdown 和文本文件
- 🔄 大文件自动分批发送（避免超出 Token 限制）
- 📏 智能 Token 估算（中文 1.5字/token，英文 4字/token）

**典型使用场景**:
```python
# 场景 1: 上传代码文件（避免截断）
shutil.copy('main.py', 'main.txt')  # 转换为 .txt
sync_context(
    operation='incremental',
    files=['main.txt'],
    project_info={'language': 'Python'}
)

# 场景 2: 上传文档供评审
sync_context(
    operation='full_sync',
    files=['README.md', 'docs/设计文档.md'],
    project_info={'task': 'code_review'}
)
```

### report_progress
报告执行进度

**参数**:
- `actions_taken`: 已执行的行动
- `result`: 执行结果（success/failed/partial）

### get_status
获取当前状态

**返回**:
- 对话历史数量
- 模型配置
- Token 限制配置

---

## 文档

| 文档 | 说明 |
|------|------|
| [用户手册](docs/用户手册.md) | 完整使用指南 |
| [安装指南](docs/CLAUDE_CODE_INSTALL.md) | Claude Code 专用安装 |
| [开发文档](docs/开发文档.md) | 技术细节和架构 |

---

## 环境变量

### 必填

| 变量 | 说明 | 示例 |
|------|------|------|
| `AURAI_API_KEY` | API 密钥 | `sk-xxx` |
| `AURAI_BASE_URL` | API 地址 | `https://open.bigmodel.cn/api/paas/v4/` |
| `AURAI_MODEL` | 模型名称 | `glm-4.7` |

### 可选

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AURAI_TEMPERATURE` | 温度参数（0.0-2.0） | `0.7` |
| `AURAI_MAX_HISTORY` | 对话历史最大保存数 | `50` |
| `AURAI_CONTEXT_WINDOW` | 上下文窗口大小（tokens） | `200000`（基于 GLM-4.7） |
| `AURAI_MAX_MESSAGE_TOKENS` | 单条消息最大 tokens | `150000` |
| `AURAI_MAX_TOKENS` | 最大输出 tokens | `32000` |

### Token 配置说明

**默认值（基于 GLM-4.7）**：
- `context_window`: 200,000 tokens
- `max_message_tokens`: 150,000 tokens
- `max_tokens`: 32,000 tokens

**其他模型参考**：
- Claude 3.5 Sonnet: 200,000 / 140,000 / 64,000
- GPT-4o: 128,000 / 100,000 / 32,000
- DeepSeek: 64,000 / 50,000 / 16,000

### 配置示例

```bash
# 使用智谱 AI GLM-4.7（推荐，使用默认值）
AURAI_API_KEY=your-api-key
AURAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
AURAI_MODEL=glm-4.7
# Token 配置使用默认值，无需设置

# 使用 Claude 3.5 Sonnet（调整 Token 配置）
AURAI_API_KEY=your-api-key
AURAI_BASE_URL=https://api.anthropic.com
AURAI_MODEL=claude-3-5-sonnet-20241022
AURAI_CONTEXT_WINDOW=200000
AURAI_MAX_MESSAGE_TOKENS=140000
AURAI_MAX_TOKENS=64000

# 使用 DeepSeek（调整 Token 配置）
AURAI_API_KEY=your-api-key
AURAI_BASE_URL=https://api.deepseek.com/v1
AURAI_MODEL=deepseek-chat
AURAI_CONTEXT_WINDOW=64000
AURAI_MAX_MESSAGE_TOKENS=50000
AURAI_MAX_TOKENS=16000

# 使用其他兼容 API
AURAI_API_KEY=your-key
AURAI_BASE_URL=https://your-api.com/v1
AURAI_MODEL=your-model
# 根据模型规格调整 Token 配置
```

---

## 项目结构

```
mcp-aurai-server/
├── src/mcp_aurai/          # MCP Server 源代码
│   ├── server.py           # 主服务器（4个工具）
│   ├── config.py           # 配置管理
│   ├── llm.py              # OpenAI 兼容客户端
│   ├── prompts.py          # 提示词模板
│   └── utils.py            # 工具函数
│
├── tools/
│   └── control_center.py   # GUI 配置工具
│
├── tests/                  # 测试用例
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
└── .env.example            # 环境变量示例
```

---

## 故障排查

### 每次打开 Claude Code 都要重新安装？

**原因**：使用了本地范围（local），只在特定目录可用。

**解决方案**：使用 `--scope user` 重新安装

```bash
claude mcp remove aurai-advisor -s local
claude mcp add --scope user ...
```

### MCP 工具没有出现

```bash
claude mcp list                          # 检查配置
claude mcp remove aurai-advisor -s local # 删除旧配置
claude mcp add --scope user ...          # 重新添加
```

### ModuleNotFoundError

```bash
cd D:\mcp-aurai-server
python -m venv venv                      # 创建虚拟环境
venv\Scripts\activate
pip install -e ".[all-dev]"              # 安装项目
```

### 401 Unauthorized
- 检查 API 密钥是否正确
- 访问提供商平台重新生成密钥

### 404 Model not found
- 检查模型名称拼写
- 使用提供商 API 确认可用模型

### 文件内容未发送给上级 AI
- 确保 `sync_context` 调用成功
- 查看日志中的 "文件已拆分为 X 个片段" 消息
- 检查 `AURAI_MAX_MESSAGE_TOKENS` 配置

---

## 测试

```bash
# 运行文件上传功能测试
python .ai_temp/test_file_upload_fix.py

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

## 获取帮助

- **用户手册**: [docs/用户手册.md](docs/用户手册.md)
- **安装指南**: [docs/CLAUDE_CODE_INSTALL.md](docs/CLAUDE_CODE_INSTALL.md)
- **开发文档**: [docs/开发文档.md](docs/开发文档.md)

---

## 许可证

MCP Aurai Server 双重许可协议

---

**项目名称**: mcp-aurai-server
**版本**: v2.2.0
**状态**: [OK] 生产就绪
**发布日期**: 2026-01-24
