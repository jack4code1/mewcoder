# MewCode

## UI Layout Note

The TUI keeps the chat area as the primary `1fr` region. The status bar sits
above the input and is shown only while the input contains text. The input box
is a compact single-line control with bounded height, so assistant output,
system messages, and tool traces remain visible in the chat area.

## Token Metrics

The status bar displays real provider token usage when the adapter receives it:

- total tokens, with prompt/completion split on wide terminals.
- average output speed in `tok/s`.
- average first-token latency as `TTFT`.
- average total API latency as `Lat`.
- `N/A` when a provider or endpoint does not return usage or a metric cannot be calculated.

Metrics are persisted in session YAML as aggregate `api_metrics`, and message-level `token_usage` is saved when available.

一个支持多种 LLM 的终端 AI 编程助手。

## 项目简介

MewCode 是一个轻量级的终端 AI 编程助手，支持多种大语言模型（LLM），提供流式对话、Markdown 渲染、会话管理等功能。

## 核心特性

- 🤖 **多模型支持** - OpenAI、Claude、Ollama、自定义端点
- ⚡ **流式对话** - 实时显示 AI 回复
- 🛠️ **工具调用** - 6 个内置工具(ReadFile / WriteFile / EditFile / Bash / Glob / Grep),让模型可以读写文件、执行命令、检索代码
- 🔁 **Agent Loop** - 支持多轮 ReAct 循环,模型可连续读文件、改文件、跑命令并根据结果继续
- 🔌 **双协议适配** - 同时支持 OpenAI tool_calls 与 Anthropic content blocks 两种 Function Calling 协议
- 📝 **Markdown 渲染** - 支持代码高亮、标题、列表等格式
- 💾 **会话持久化** - YAML 格式保存对话历史
- 🎯 **命令补全** - Tab 补全内置命令
- 📊 **状态监控** - 实时显示 Token 用量、会话时长等信息
- 🧠 **项目上下文与记忆** - Token 预算、上下文概览和项目级记忆命令
- 📚 **项目 Skills** - 自动加载 `.mewcode/skills/*.md` 作为可复用项目指令
- 🔒 **可选安全审批** - 启用后，状态变更工具需经会话或项目级授权，并保留审计记录

---

## 项目框架

### 五层架构

```
┌─────────────────────────────────────────────────────────────┐
│  交互层 (TUI)                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Textual 框架                                         │  │
│  │  - ChatArea: 对话区域（Markdown 渲染、流式显示）      │  │
│  │  - StatusBar: 状态栏（模型、Token、时长，位于输入框   │  │
│  │    上方，输入时显示、无输入时隐藏）                    │  │
│  │  - InputBox: 输入框（历史命令、命令补全，至少一行）    │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  引擎层 (Engine)                                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  LLM 客户端                                           │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │  │
│  │  │ OpenAI  │ │ Claude  │ │ Ollama  │ │ Custom  │    │  │
│  │  │ Adapter │ │ Adapter │ │ Adapter │ │ Adapter │    │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │ AdapterFactory - 自动检测模型提供商             │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │ ConversationManager - 会话管理、Token 统计      │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  工具层 (Tools)                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  - 文件读写工具                                       │  │
│  │  - 命令执行工具                                       │  │
│  │  - 代码搜索工具                                       │  │
│  │  - Git 操作工具                                       │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  记忆层 (Memory)                                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  - 项目上下文管理                                     │  │
│  │  - 对话历史索引                                       │  │
│  │  - 用户偏好存储                                       │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  安全层 (Security)                                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  - 命令确认机制                                       │  │
│  │  - 文件 diff 预览                                     │  │
│  │  - 操作回滚                                           │  │
│  │  - 沙箱执行                                           │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 模块说明

#### 1. 交互层 (TUI)

基于 [Textual](https://textual.textualize.io/) 框架构建的终端用户界面。

| 组件 | 文件 | 功能 |
|------|------|------|
| ChatArea | `tui/widgets/chat_area.py` | 对话区域，支持 Markdown 渲染和流式显示 |
| InputBox | `tui/widgets/input_box.py` | 输入框，支持历史命令、命令补全 |
| StatusBar | `tui/widgets/status_bar.py` | 状态栏，位于输入框上方；输入时显示模型、Token、会话时长等信息，无输入时隐藏且不占布局空间 |
| MewCodeApp | `tui/app.py` | 主应用，管理组件生命周期和事件处理 |

#### 2. 引擎层 (Engine)

LLM 客户端和对话管理的核心模块。

**数据模型** (`engine/models/`)
- `Message` - 对话消息
- `MessageRole` - 消息角色（user/assistant/system）
- `TokenUsage` - Token 用量统计
- `LLMResponse` - LLM 响应
- `StreamChunk` - 流式响应块
- `LLMClient` - LLM 客户端抽象基类

**适配器** (`engine/adapters/`)
- `OpenAIAdapter` - OpenAI API 适配器
- `ClaudeAdapter` - Claude API 适配器
- `OllamaAdapter` - Ollama 本地模型适配器
- `CustomAdapter` - 自定义端点适配器（支持 OpenAI 兼容协议）
- `AdapterFactory` - 适配器工厂，自动检测模型提供商

**对话管理** (`engine/conversation.py`)
- `Conversation` - 单个对话
- `ConversationManager` - 对话管理器，支持会话持久化

#### 3. 工具层 (Tools)

工具子系统让模型从「只能动嘴」升级到「能动手」。模型在对话中可以请求工具,本地执行,把结果回灌让模型基于真实数据继续回答。

**核心抽象** (`engine/tools/`)

| 组件 | 文件 | 职责 |
|------|------|------|
| `Tool` 抽象基类 | `base.py` | 工具接口:name / description / input_schema / category / 元信息 / validate_input / execute |
| `ToolResult` | `base.py` | 工具返回值,is_error 区分成功/可恢复错误 |
| `ToolContext` | `base.py` | 启动时锁定的运行上下文(working_dir / OS / shell) |
| `ToolError` | `base.py` | 系统级错误标记(可恢复错误不抛此异常) |
| `ToolRegistry` | `registry.py` | 注册中心 + 双协议格式输出 + 调度执行 + 错误兜底 |
| `build_system_prompt` | `system_prompt.py` | 构造英文 system prompt(cwd / OS / 工具使用原则) |

**6 个内置工具**

| 工具 | 分类 | 只读 | 描述 |
|------|------|------|------|
| `ReadFile` | file | ✓ | 读文件(带行号),支持 offset/limit 分段,拒绝二进制 |
| `WriteFile` | file | ✗ | 写文件,自动创建父目录,覆盖已存在 |
| `EditFile` | file | ✗ | 局部替换,要求 old_string 在文件中唯一匹配 |
| `Bash` | shell | ✗ | 执行 shell 命令(默认 30s 超时,输出截断) |
| `Glob` | search | ✓ | 按 glob 找文件,排除噪音目录,按 mtime 倒序 |
| `Grep` | search | ✓ | 正则搜内容,跳过二进制,支持 include / 上下文行 |

**Agent Loop 多步流程**

```
用户输入 → LLM → 模型请求工具 → 本地执行 → 结果回灌 → LLM → ...
             ↑                                               │
             └──────────── 直到模型不再请求工具或触发停止条件 ┘

运行期间 TUI 通过 AgentEvent 实时展示文本、工具调用、工具结果和状态。
```

**协议适配**(在 Adapter 内部完成翻译,上层不感知协议差异)

- **OpenAI 协议族**(CustomAdapter / OpenAIAdapter / OllamaAdapter):`tool_calls` + `role:tool`
- **Anthropic 协议**(ClaudeAdapter):`tool_use` / `tool_result` content blocks

**配置**(`config.yaml`)

```yaml
tools:
  enabled: "all"        # "all" | "readonly" | [ReadFile, Glob, Grep, ...]
  bash_timeout: 30
  max_output_chars: 10000
```

#### 4. 上下文与项目记忆

当前应用会在每次请求中按 Token 预算裁剪上下文，并支持 `/context` 查看预算摘要。`/memory`、`/remember` 和 `/forget` 管理项目级记忆；记忆会作为 system context 注入后续请求。

#### 5. 安全审批（可选）

写文件、编辑文件和命令执行默认通过审批网关；只读工具无需确认。TUI 提供单次请求、会话和项目级授权，以及 `/audit` 审计查看。仅可信自动化场景应在被忽略的 `config.local.yaml` 中显式设置 `security.enabled: false`。

#### 6. 扩展能力状态

MCP、Skill、Hook、任务编排、Worktree 和 Agent Teams 已有隔离的基础数据结构或适配层，但尚未接入完整的 TUI 用户工作流，不能视为可用产品功能。

---

## 目录结构

```
mewcode/
├── pyproject.toml              # 项目配置
├── config.yaml                 # 运行时配置
├── start.ps1                   # PowerShell 启动脚本
├── start.bat                   # CMD 启动脚本
├── src/
│   └── mewcode/
│       ├── __init__.py
│       ├── main.py             # 主入口
│       ├── cli.py              # CLI 接口
│       ├── config.py           # 配置加载
│       ├── logger.py           # 日志配置
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── agent.py       # ReAct Agent Loop
│       │   ├── agent_events.py # AgentEvent 事件模型
│       │   ├── conversation.py # 会话管理
│       │   ├── models/
│       │   │   ├── client.py   # LLM 客户端接口
│       │   │   └── message.py  # 消息数据模型
│       │   └── adapters/
│       │       ├── factory.py  # 适配器工厂
│       │       ├── _openai_protocol.py  # OpenAI tool_calls 翻译/聚合的共享 helper
│       │       ├── openai_adapter.py
│       │       ├── claude_adapter.py
│       │       ├── ollama_adapter.py
│       │       └── custom_adapter.py
│       ├── engine/tools/         # 工具子系统(02-tools 章节)
│       │   ├── base.py           # Tool/ToolResult/ToolContext/ToolError
│       │   ├── registry.py       # ToolRegistry
│       │   ├── system_prompt.py  # 英文 system prompt 构造
│       │   ├── read_file.py
│       │   ├── write_file.py
│       │   ├── edit_file.py
│       │   ├── bash.py
│       │   ├── glob.py
│       │   └── grep.py
│       └── tui/
│           ├── app.py          # TUI 主应用(消费 AgentEvent)
│           └── widgets/
│               ├── chat_area.py    # 含工具调用轨迹渲染
│               ├── input_box.py
│               └── status_bar.py
├── specs/                      # 章节化规格文档
│   ├── 02-tools/               # 工具系统(单步)
│   └── 04-agent-loop/          # Agent Loop 多步循环
│       ├── spec.md             # 需求(F/N/AC)
│       ├── plan.md             # 架构设计与决策
│       ├── task.md             # 任务拆解与依赖图
│       └── checklist.md        # 验收清单
└── tests/
    ├── test_e2e.py
    ├── test_message_tool_calls.py
    ├── test_adapter_tool_calls.py
    ├── test_adapter_anthropic_tool_use.py
    └── test_tools_*.py          # 8 个工具单测文件
```

---

## 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.10+ | 编程语言 |
| Textual | TUI 框架 |
| Rich | 富文本渲染 |
| httpx | HTTP 客户端 |
| PyYAML | 配置管理 |
| pytest | 测试框架 |

---

## 快速开始

### 安装依赖

```bash
python -m venv .venv
# macOS/Linux
.venv/bin/python -m pip install -e ".[dev]"
# Windows PowerShell
.venv\Scripts\python -m pip install -e ".[dev]"
```

### 启动 MewCode

```bash
mewcode
# 或
python -m mewcode
```

### 配置 API

编辑 `config.yaml` 文件，配置你的 API 密钥。推荐把密钥放在环境变量中；如果环境变量不存在或为空，MewCode 会继续使用 `api_key` 里的明文 fallback。

```yaml
llm:
  default_model: "mimo-v2.5-pro"
  default_provider: "custom"

  models:
    mimo-v2.5-pro:
      provider: "custom"
      base_url: "https://your-api-endpoint.com/v1"
      api_key_env: "MIMO_API_KEY"
      api_key: "your-api-key-fallback"
      api_format: "openai"
      model: "mimo-v2.5-pro"
```

PowerShell 示例：

```powershell
$env:MIMO_API_KEY="your-api-key"
.\start.ps1
```

---

## 内置命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/clear` | 清空对话 |
| `/save` | 保存当前会话 |
| `/copy` | 复制最后一条 AI 回复 |
| `/mode` | 切换对话/单次模式 |
| `/context` | 查看当前上下文预算摘要 |
| `/memory` | 查看项目记忆 |
| `/remember <内容>` | 保存项目记忆 |
| `/forget <id>` | 删除项目记忆 |
| `/skills` | 查看已加载的项目 Skills |
| `/mcp` | 查看已配置 MCP 服务 |
| `/mcp connect <name>` | 显式连接启用的 MCP 服务 |
| `/task <目标>` | 在隔离 Worktree 中运行子任务 |
| `/tasks` | 查看子任务结果 |
| `/task apply <id>` | 应用子任务 diff |
| `/task discard <id>` | 丢弃子任务 Worktree |
| `/diff` | 查看可回滚 revision |
| `/rollback <id>` | 回滚一个 revision |
| `/memory search <查询>` | 搜索项目记忆 |
| `/summarize` | 压缩较早会话历史 |
| `/skill add <名称> <指令>` | 创建项目 Skill |
| `/skill delete <名称>` | 删除项目 Skill |
| `/audit` | 查看最近安全审计记录（启用安全模式时） |
| `/quit` | 退出程序 |

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Enter` | 发送消息并清空输入栏 |
| `Ctrl+C` | 退出程序 |
| `Ctrl+S` | 保存会话 |
| `Ctrl+Shift+C` | 复制最后一条 AI 回复 |
| `Esc` | 取消当前 Agent Loop,不退出程序 |
| `↑` / `↓` | 浏览历史提示词 |
| `Tab` | 命令补全 |

---

## 版本历史

- **v0.2** - Agent Loop 多步循环
  - 新增引擎层 Agent Loop 和 AgentEvent 事件流
  - 支持多轮工具调用,不再忽略第二轮 tool_calls
  - 支持 50 轮迭代上限、重复无效工具终止和 Esc 取消
  - 修复 Enter 提交后输入栏不清空、上下方向键切换历史提示词问题

- **v0.1** - 工具系统(单步)
  - 6 个内置工具:ReadFile / WriteFile / EditFile / Bash / Glob / Grep
  - 同时支持 OpenAI tool_calls 与 Anthropic content blocks 协议
  - 流式 tool_calls / tool_use 增量聚合
  - 单步工具调用流程:模型请求 → 本地执行 → 结果回灌 → 最终回复
  - TUI 工具调用轨迹展示(`→` `✓` `✗` 三态)
  - `config.yaml` 工具开关(all / readonly / 显式列表)
  - 工具子系统全英文输入输出,面向用户的 TUI 文案中文
  - 单元测试覆盖工具、协议翻译、流式聚合(总 133 case)

- **v0.0** - 初始版本
  - 多 LLM 支持(OpenAI、Claude、Ollama、自定义端点)
  - 流式对话
  - Markdown 渲染
  - 会话持久化
  - TUI 界面

---

## 许可证

MIT License
