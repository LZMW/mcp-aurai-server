# MCP 安装配置知识集

> 基于 Claude Code 官方文档整理
> 版本: v1.0 | 更新日期: 2026-01-22

---

## 目录

1. [MCP 核心概念](#1-mcp-核心概念)
2. [三种传输方式](#2-三种传输方式)
3. [三种配置范围](#3-三种配置范围)
4. [安装命令详解](#4-安装命令详解)
5. [MCP 资源引用](#5-mcp-资源引用)
6. [MCP 提示命令](#6-mcp-提示命令)
7. [身份验证](#7-身份验证)
8. [托管配置](#8-托管配置)
9. [故障排查](#9-故障排查)
10. [常用命令速查](#10-常用命令速查)

---

## 1. MCP 核心概念

### 什么是 MCP？

**MCP (Model Context Protocol)** 是一个开源标准，让 Claude Code 能够连接到数百个外部工具和数据源（数据库、API、问题跟踪器等）。

### MCP 可以做什么？

- **从问题跟踪器实现功能**："添加 JIRA 问题 ENG-4521 中描述的功能"
- **分析监控数据**："检查 Sentry 和 Statsig 的使用情况"
- **查询数据库**："根据 PostgreSQL 数据库查找用户"
- **集成设计**："根据 Figma 设计更新邮件模板"
- **自动化工作流**："创建 Gmail 草稿邀请用户"

---

## 2. 三种传输方式

### HTTP 服务器（推荐）

**适用场景**: 云服务、远程 API

```bash
# 基本语法
claude mcp add --transport http <name> <url>

# 示例：连接 Notion
claude mcp add --transport http notion https://mcp.notion.com/mcp

# 带 Bearer 令牌
claude mcp add --transport http secure-api https://api.example.com/mcp \
  --header "Authorization: Bearer your-token"
```

### SSE 服务器（已弃用）

> ⚠️ SSE 传输已弃用，请在可用的地方使用 HTTP 服务器。

```bash
claude mcp add --transport sse <name> <url>
```

### Stdio 服务器（本地进程）

**适用场景**: 需要系统访问、自定义脚本

```bash
# 基本语法
claude mcp add [options] <name> -- <command> [args...]

# 示例：添加 Airtable 服务器
claude mcp add --transport stdio --env AIRTABLE_API_KEY=YOUR_KEY airtable \
  -- npx -y airtable-mcp-server

# 示例：Python MCP 服务器
claude mcp add --transport stdio my-server \
  --env API_KEY=sk-xxx \
  -- "D:\project\venv\Scripts\python.exe" "-m" "my_mcp.server"
```

#### Windows 用户注意事项

在 Windows 上使用 `npx` 的 stdio 服务器需要 `cmd /c` 包装器：

```bash
claude mcp add --transport stdio my-server -- cmd /c npx -y @some/package
```

---

## 3. 三种配置范围

### 范围对比表

| 范围 | 命令参数 | 存储位置 | 可用性 | 适用场景 |
|------|----------|----------|--------|----------|
| **本地** | `--scope local` (默认) | `~/.claude.json` 项目路径 | 仅当前项目目录 | 临时测试 |
| **项目** | `--scope project` | `.mcp.json` (项目根目录) | 团队共享 | 团队协作 |
| **用户** | `--scope user` | `~/.claude.json` 用户配置 | ✅ 所有项目 | ✅ 个人工具 |

### 本地范围（Local）

```bash
# 默认范围，仅在当前项目目录可用
claude mcp add --transport http stripe https://mcp.stripe.com

# 显式指定
claude mcp add --transport http stripe --scope local https://mcp.stripe.com
```

- 存储：`~/.claude.json` 的项目路径下
- 适用：个人开发服务器、实验配置
- 问题：切换目录后不可用

### 项目范围（Project）

```bash
# 团队共享，存储在项目根目录
claude mcp add --transport http paypal --scope project https://mcp.paypal.com/mcp
```

- 存储：项目根目录的 `.mcp.json`
- 适用：团队共享的服务器、项目特定工具
- 注意：首次使用需要批准

**生成的 `.mcp.json` 文件**：
```json
{
  "mcpServers": {
    "shared-server": {
      "type": "http",
      "url": "https://api.example.com/mcp"
    }
  }
}
```

### 用户范围（User）

```bash
# 跨项目可用，个人工具推荐
claude mcp add --transport http hubspot --scope user https://mcp.hubspot.com/anthropic
```

- 存储：`~/.claude.json`
- 适用：个人实用工具、经常使用的服务
- 优势：任何项目都能用

### 范围优先级

当同名服务器存在于多个范围时：**local > project > user**

---

## 4. 安装命令详解

### 命令结构

```
claude mcp add [选项] <服务器名称> -- <命令> [参数...]
```

### 选项顺序（重要！）

⚠️ **所有选项必须放在服务器名称之前，`--` 分隔服务器命令**

```bash
# ✅ 正确
claude mcp add --transport stdio --env KEY=value myserver -- npx server

# ❌ 错误（选项在名称之后）
claude mcp add myserver --transport stdio --env KEY=value -- npx server
```

### 常用选项

| 选项 | 说明 | 示例 |
|------|------|------|
| `--transport` | 传输类型 | `http`, `sse`, `stdio` |
| `--scope` | 配置范围 | `local`, `project`, `user` |
| `--env` | 环境变量 | `--env KEY=value` |
| `--header` | HTTP 请求头 | `--header "Authorization: Bearer token"` |

### 环境变量设置

```bash
# 单个环境变量
claude mcp add --transport stdio server --env API_KEY=xxx ...

# 多个环境变量
claude mcp add --transport stdio server \
  --env API_KEY=xxx \
  --env API_URL=https://api.com \
  ...
```

### 完整安装示例

```bash
# HTTP 服务器（用户范围）
claude mcp add --scope user --transport http github \
  https://api.githubcopilot.com/mcp/

# Stdio 服务器（用户范围，带环境变量）
claude mcp add --scope user --transport stdio aurai-advisor \
  --env AURAI_API_KEY=sk-xxx \
  --env AURAI_PROVIDER=custom \
  --env AURAI_BASE_URL=https://api.com/v1 \
  -- "D:\project\venv\Scripts\python.exe" "-m" "mcp_aurai.server"
```

---

## 5. MCP 资源引用

### 引用 MCP 资源

MCP 服务器可以公开资源，使用 `@` 引用：

```
> Can you analyze @github:issue://123 and suggest a fix?
> Please review the API documentation at @docs:file://api/authentication
```

### 引用格式

`@server:protocol://resource/path`

### 多资源引用

```
> Compare @postgres:schema://users with @docs:file://database/user-model
```

### 资源特点

- 引用时自动获取
- 路径支持模糊搜索
- 可包含文本、JSON、结构化数据

---

## 6. MCP 提示命令

### 执行 MCP 提示

MCP 服务器可以公开提示，作为斜杠命令可用：

```
> /mcp__github__list_prs
> /mcp__github__pr_review 456
> /mcp__jira__create_issue "Bug in login flow" high
```

### 提示命名格式

`/mcp__servername__promptname`

### 发现可用提示

在 Claude Code 中输入 `/` 查看所有可用命令，包括 MCP 提示。

---

## 7. 身份验证

### OAuth 2.0 流程

#### 步骤 1：添加需要认证的服务器

```bash
claude mcp add --transport http sentry https://mcp.sentry.dev/mcp
```

#### 步骤 2：在 Claude Code 中认证

```
> /mcp
```

然后按照浏览器中的步骤登录。

### 认证特点

- 令牌安全存储，自动刷新
- 使用 `/mcp` 菜单中的 "Clear authentication" 撤销访问
- 适用于 HTTP 服务器

---

## 8. 托管配置

### 企业级控制选项

#### 选项 1：managed-mcp.json（独占控制）

**系统路径**：
- macOS: `/Library/Application Support/ClaudeCode/managed-mcp.json`
- Linux/WSL: `/etc/claude-code/managed-mcp.json`
- Windows: `C:\Program Files\ClaudeCode\managed-mcp.json`

**配置示例**：
```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/"
    },
    "company-internal": {
      "type": "stdio",
      "command": "/usr/local/bin/company-mcp-server",
      "args": ["--config", "/etc/company/mcp-config.json"],
      "env": {
        "COMPANY_API_URL": "https://internal.company.com"
      }
    }
  }
}
```

**特点**：
- 用户无法添加、修改或使用此文件外的 MCP 服务器
- 适用于需要完全控制的组织

#### 选项 2：允许列表/拒绝列表（基于策略）

在托管设置文件中使用 `allowedMcpServers` 和 `deniedMcpServers`：

```json
{
  "allowedMcpServers": [
    // 按服务器名称允许
    { "serverName": "github" },
    { "serverName": "sentry" },

    // 按命令允许（stdio 服务器）
    { "serverCommand": ["npx", "-y", "@modelcontextprotocol/server-filesystem"] },

    // 按 URL 模式允许（远程服务器）
    { "serverUrl": "https://mcp.company.com/*" },
    { "serverUrl": "https://*.internal.corp/*" }
  ],
  "deniedMcpServers": [
    { "serverName": "dangerous-server" },
    { "serverUrl": "https://*.untrusted.com/*" }
  ]
}
```

**限制方式**：
- 按服务器名称 (`serverName`)
- 按命令 (`serverCommand`)
- 按 URL 模式 (`serverUrl`)

---

## 9. 故障排查

### 常见问题

#### 问题：每次打开 Claude Code 都要重新安装

**原因**：使用了默认的本地范围（local）

**解决方案**：
```bash
claude mcp remove <server> -s local
claude mcp add --scope user ...
```

#### 问题：MCP 工具没有出现

**排查步骤**：
```bash
# 1. 检查配置
claude mcp list

# 2. 查看详细配置
claude mcp get <server>

# 3. 删除并重新添加
claude mcp remove <server> -s local
claude mcp add --scope user ...
```

#### 问题：Connection closed（Windows）

**原因**：Windows 无法直接执行 `npx`

**解决方案**：
```bash
# 使用 cmd /c 包装器
claude mcp add --transport stdio my-server -- cmd /c npx -y @package
```

#### 问题：ModuleNotFoundError

**原因**：虚拟环境未创建或项目未安装

**解决方案**：
```bash
cd D:\mcp-aurai-server
python -m venv venv
venv\Scripts\activate
pip install -e ".[all-dev]"
```

### 环境变量扩展

`.mcp.json` 支持环境变量扩展：

```json
{
  "mcpServers": {
    "api-server": {
      "type": "http",
      "url": "${API_BASE_URL:-https://api.example.com}/mcp",
      "headers": {
        "Authorization": "Bearer ${API_KEY}"
      }
    }
  }
}
```

**语法**：
- `${VAR}` - 扩展为环境变量值
- `${VAR:-default}` - 如果未设置则使用默认值

---

## 10. 常用命令速查

### 管理命令

```bash
# 列出所有服务器
claude mcp list

# 获取服务器详细信息
claude mcp get <name>

# 删除服务器
claude mcp remove <name> [-s local|project|user]

# 检查服务器状态（Claude Code 中）
/mcp
```

### 配置命令

```bash
# 添加 HTTP 服务器（用户范围）
claude mcp add --scope user --transport http <name> <url>

# 添加 Stdio 服务器（用户范围）
claude mcp add --scope user --transport stdio <name> --env KEY=value -- <command> [args]

# 从 JSON 添加
claude mcp add-json <name> '<json>'

# 从 Claude Desktop 导入
claude mcp add-from-claude-desktop
```

### 故障排查命令

```bash
# 重置项目批准选择
claude mcp reset-project-choices

# 查看 MCP 输出限制
echo $MAX_MCP_OUTPUT_TOKENS

# 设置输出限制（增加限制）
export MAX_MCP_OUTPUT_TOKENS=50000
```

### 验证命令

```bash
# 检查连接状态
claude mcp list

# 查看服务器作用域
claude mcp get <name>
# 应显示：Scope: User config (available in all your projects)
```

---

## 附录

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MCP_TIMEOUT` | MCP 服务器启动超时（毫秒） | 无限制 |
| `MAX_MCP_OUTPUT_TOKENS` | MCP 输出令牌限制 | 25000 |
| `CLAUDE_PLUGIN_ROOT` | 插件根目录路径 | - |

### 配置文件位置

| 配置类型 | 存储位置 |
|----------|----------|
| 用户/本地范围 | `~/.claude.json` |
| 项目范围 | 项目根目录 `.mcp.json` |
| 托管配置 | 系统目录 `managed-mcp.json` |

### MCP 输出警告

- **警告阈值**：10,000 tokens
- **默认最大值**：25,000 tokens
- **增加限制**：`export MAX_MCP_OUTPUT_TOKENS=50000`

---

## 重点强调

### ⚠️ --scope user 是关键！

**为什么必须使用 `--scope user`？**

| 不使用 | 使用 |
|--------|------|
| 每次切换目录都要重新安装 | ✅ 所有项目都能用 |
| 只在特定目录可用 | ✅ 任意目录自动可用 |
| 容易误以为 MCP 坏了 | ✅ 体验稳定可靠 |

**标准安装命令模板**：

```bash
# HTTP 服务器
claude mcp add --scope user --transport http <name> <url>

# Stdio 服务器
claude mcp add --scope user --transport stdio <name> \
  --env KEY=value \
  -- <command> [args]
```

**检查是否使用了 user scope**：

```bash
claude mcp get <name>
# 应该显示：Scope: User config (available in all your projects)
```

**修复方法**（如果没用 user scope）：

```bash
claude mcp remove <name> -s local
claude mcp add --scope user ...
```

---

**知识集版本**: v1.0
**基于**: Claude Code 官方 MCP 文档
**最后更新**: 2026-01-22
