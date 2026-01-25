# 更新日志 v2.2.0

**发布日期**: 2026-01-24
**版本**: v2.2.0
**类型**: 重大重构 + Bug 修复
**优化模型**: GLM-4.7

---

## 概述

本次更新是一次**重大重构**，主要解决了 `sync_context` 文件上传功能的核心问题，简化了服务商支持架构，并针对 **GLM-4.7** 模型进行了硬编码优化。

---

## 核心修复

### 1. 文件上传功能修复 ⭐

**问题描述**：`sync_context` 工具读取的文件内容完全没有发送给上级 AI

**根本原因**：
- `server.py` 中 `sync_context` 确实读取了文件内容并存储
- 但 `llm.py` 的 `_build_messages_from_history` 函数直接跳过了 `sync_context` 类型记录
- 文件内容被存储但从未传递给 API

**修复方案**：
- ✅ 重写 `_build_messages_from_history` 函数
- ✅ 将 `sync_context` 的文件内容转换为 `system` 消息发送
- ✅ 实现大文件自动分批发送机制
- ✅ 添加 Token 估算功能

**测试结果**：
```
✅ 配置值测试通过
✅ Token 估算测试通过
✅ 小文件拆分测试通过
✅ 大文件拆分测试通过 (2 个片段)
✅ 对话历史构建测试通过
```

---

## 重大变更

### 2. 简化服务商支持

**变更内容**：
- ✅ 只保留 `custom` provider（OpenAI 兼容 API）
- ❌ 移除 `zhipu`、`openai`、`anthropic`、`gemini` 直接支持
- ✅ 所有兼容 OpenAI API 的服务均可使用

**影响范围**：
| 文件 | 变更 |
|------|------|
| `config.py` | provider 类型简化为 `Literal["custom"]` |
| `llm.py` | 删除所有非 custom 服务商代码（~400 行） |
| `pyproject.toml` | 移除 zhipuai、anthropic、google-generativeai 依赖 |

**代码简化统计**：
- 删除代码行数：~400 行
- 新增代码行数：~150 行
- 净减少：~250 行

---

## 新增功能

### 3. GLM-4.7 模型硬编码优化 🎯

**设计理念**：采用 GLM-4.7 参数作为默认值，同时保留用户通过环境变量覆盖的灵活性。

**GLM-4.7 模型规格**（来自智谱 AI 官方文档）：
| 参数 | 值 |
|------|-----|
| 上下文窗口 | 200,000 tokens |
| 最大输出 | 128,000 tokens |

**硬编码配置**（方案 A - 保守型）：

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `context_window` | 200,000 | GLM-4.7 上下文窗口上限 |
| `max_message_tokens` | 150,000 | 单条文件消息上限 |
| `max_tokens` | 32,000 | 上级 AI 最大输出长度 |

**Token 分配策略**：
```
200K (总上下文)
├── 32K (输出) - 上级 AI 的分析回复
└── 168K (输入)
    ├── ~18K (系统提示词 + 对话历史 + 用户问题)
    ├── 150K (最大单条文件消息)
    └── ~ - 安全边际
```

**容量参考**：
- 单文件上传上限：~15-20 万中文字符
- 上级 AI 输出上限：~2-3 万中文字符
- 对话历史：约 10-15 轮完整对话

**代码实现**（`config.py`）：
```python
# GLM-4.7 模型参数配置（基于智谱 GLM-4.7 规格的默认值）
DEFAULT_CONTEXT_WINDOW = 200000        # GLM-4.7 上下文窗口上限
DEFAULT_MAX_MESSAGE_TOKENS = 150000    # 单条文件消息上限
DEFAULT_MAX_TOKENS = 32000             # 上级 AI 最大输出

# 用户可通过环境变量覆盖（适用于其他模型）
context_window: int = Field(
    default_factory=lambda: int(os.getenv("AURAI_CONTEXT_WINDOW", str(DEFAULT_CONTEXT_WINDOW)))
)
max_message_tokens: int = Field(...)
max_tokens: int = Field(...)
```

### 4. Token 估算与分批发送

**新增方法**：

`AuraiClient._estimate_tokens(text: str) -> int`
- 中文：约 1.5 字符/token
- 英文：约 4 字符/token

`AuraiClient._split_file_content(file_path: str, content: str) -> list[str]`
- 自动检测文件大小
- 超过 `max_message_tokens` 自动拆分
- 保留完整内容，不丢失数据

**消息格式**：
```python
# 小文件（单条消息）
{"role": "system", "content": "## 已上传文件\n\n### 文件: main.py\n```...```"}

# 大文件（分批发送）
{"role": "system", "content": "## 已上传文件 (1/3)\n\n### 文件: main.py (第 1/3 部分)\n```...```"}
{"role": "system", "content": "## 已上传文件 (2/3)\n\n### 文件: main.py (第 2/3 部分)\n```...```"}
{"role": "system", "content": "## 已上传文件 (3/3)\n\n### 文件: main.py (第 3/3 部分)\n```...```"}
```

---

## 依赖变更

### 移除的依赖
- `zhipuai>=2.0.0`
- `anthropic>=0.18.0`
- `google-generativeai>=0.3.0`

### 保留的依赖
- `fastmcp>=0.1.0`
- `pydantic>=2.0.0`
- `python-dotenv>=1.0.0`
- `openai>=1.0.0`
- `httpx>=0.24.0` （新增，用于 HTTP 超时配置）

---

## 配置迁移指南

### 从 v2.1.x 升级到 v2.2.0

**如果使用 custom provider（无需更改）**：
```bash
# 配置保持不变
AURAI_PROVIDER=custom
AURAI_API_KEY=sk-xxx
AURAI_BASE_URL=https://api.example.com/v1
AURAI_MODEL=your-model
```

**如果使用其他 provider（需要迁移）**：
```bash
# 旧配置（v2.1.x）
AURAI_PROVIDER=zhipu
AURAI_MODEL=glm-4-flash

# 新配置（v2.2.0）- 使用兼容 API
AURAI_PROVIDER=custom
AURAI_API_KEY=your-key
AURAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
AURAI_MODEL=glm-4-flash
```

**各服务商迁移方案**：

| 原提供商 | Base URL |
|---------|----------|
| zhipu | `https://open.bigmodel.cn/api/paas/v4/` |
| openai | `https://api.openai.com/v1` |
| anthropic | 需使用第三方兼容 API |
| gemini | 需使用第三方兼容 API |

---

## 文件变更清单

### 修改的文件
- `README.md` - 更新版本信息、移除多提供商说明
- `pyproject.toml` - 更新版本号、清理依赖
- `src/mcp_aurai/config.py` - 简化 provider、新增 Token 配置
- `src/mcp_aurai/llm.py` - 完全重写，只保留 custom

### 新增的文件
- `.ai_temp/test_file_upload_fix.py` - 文件上传功能测试
- `CHANGELOG_v2.2.md` - 本文件

### 删除的功能
- 多 provider 切换功能
- `get_models()` 中的多提供商支持

---

## 向后兼容性

### ✅ 完全兼容
- `custom` provider 用户无需任何更改
- 环境变量配置保持一致
- MCP 工具接口不变

### ❌ 不兼容变更
- 移除了 `zhipu`、`openai`、`anthropic`、`gemini` provider
- 需要迁移到 `custom` + 对应的 Base URL

---

## 已知问题

暂无

---

## 下一计划

- [ ] 性能优化：减少重复的 Token 估算
- [ ] 功能增强：支持二进制文件的 base64 编码上传
- [ ] 用户体验：添加文件上传进度提示

---

## 致谢

感谢用户反馈发现了 `sync_context` 文件内容未发送的问题，这是本次更新的核心驱动力。
