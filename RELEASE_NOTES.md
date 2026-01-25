# MCP Aurai Advisor v2.2.0 发布说明

**发布日期**: 2026-01-24
**版本**: v2.2.0
**类型**: 重大重构 + Bug 修复

---

## 📦 发布内容

### 项目位置
```
C:\Users\29493\Desktop\mcp-aurai-server
```

### Git 状态
- ✅ 所有更改已提交到 git
- ✅ 敏感信息已清理（API 密钥、对话历史、缓存文件）
- ✅ .gitignore 已配置（忽略 .env、.mcp-aurai/、.ai_temp/ 等）

---

## 🎯 本版本更新

### 1. 简化服务商支持
- ✅ 只保留 `custom` provider（OpenAI 兼容 API）
- ❌ 移除 zhipu、openai、anthropic、gemini 直接支持
- ✅ 所有兼容 OpenAI API 的服务均可使用

### 2. 文件上传功能修复 ⭐
- ✅ 修复 `sync_context` 文件内容未发送给上级 AI 的问题
- ✅ 大文件自动分批发送（超过 `max_message_tokens` 时）
- ✅ 动态 Token 估算，根据配置自动调整

### 3. GLM-4.7 模型优化 🎯
- ✅ 基于 GLM-4.7 模型参数设置默认值
- ✅ 上下文窗口：200,000 tokens（默认）
- ✅ 单条消息上限：150,000 tokens（默认）
- ✅ 最大输出：32,000 tokens（默认）
- ✅ 支持通过环境变量覆盖（适用于其他模型）

---

## 📁 项目结构

```
mcp-aurai-server/
├── src/mcp_aurai/          # 源代码
│   ├── config.py           # 配置管理（GLM-4.7 默认值 + 环境变量覆盖）
│   ├── llm.py              # OpenAI 兼容客户端（文件分批发送）
│   ├── server.py           # MCP 服务器（4个工具）
│   ├── prompts.py          # 提示词模板
│   └── utils.py            # 工具函数
├── tools/
│   └── control_center.py   # GUI 配置工具（已更新）
├── tests/                  # 测试用例
├── docs/                   # 文档
├── README.md               # 项目说明
├── CHANGELOG_v2.2.md       # 更新日志
├── .env.example            # 环境变量示例
├── pyproject.toml          # 项目配置（v2.2.0）
└── LICENSE                 # 许可证
```

---

## 🔑 安全清理

### 已清理内容
- ✅ `.env` - 删除（包含 API 密钥）
- ✅ `.mcp-aurai/history.json` - 删除（对话历史）
- ✅ `.ai_temp/` - 删除（临时文件和测试脚本）
- �__pycache__/ - 删除（Python 缓存）
- ✅ `*.pyc` - 删除（Python 字节码缓存）
- ✅ CHANGELOG_v2.1.md - 删除（旧版本日志）

### .gitignore 配置
```
.env                      # API 密钥
.mcp-aurai/              # 对话历史
.ai_temp/                # 临时文件
*.pyc                     # Python 缓存
__pycache__/              # Python 缓存目录
```

---

## 📋 发布前检查清单

- [x] 版本号更新为 v2.2.0
- [x] README.md 更新完成
- [x] CHANGELOG_v2.2.md 创建完成
- [x] .env.example 更新（无敏感信息）
- [x] 源码已清理（无密钥、无缓存）
- [x] Git 提交已创建
- [ ] 推送到 GitHub（待执行）

---

## 🚀 推送命令

```bash
# 确认当前分支
cd C:\Users\29493\Desktop\mcp-aurai-server
git branch

# 推送到远程仓库
git push origin main

# 或首次推送
# git push -u origin main
```

---

## 📝 待用户确认

项目已准备好推送到 GitHub，是否现在推送？
