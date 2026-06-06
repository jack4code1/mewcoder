# MewCode

一个支持多种 LLM 的终端 AI 编程助手。

## 项目简介

MewCode 是一个轻量级的终端 AI 编程助手，支持多种大语言模型（LLM），提供流式对话、Markdown 渲染、会话管理等功能。

## 核心特性

- 🤖 **多模型支持** - OpenAI、Claude、Ollama、自定义端点
- ⚡ **流式对话** - 实时显示 AI 回复
- 📝 **Markdown 渲染** - 支持代码高亮、标题、列表等格式
- 💾 **会话持久化** - YAML 格式保存对话历史
- 🎯 **命令补全** - Tab 补全内置命令
- 📊 **状态监控** - 实时显示 Token 用量、会话时长等信息

---

## 项目框架

### 五层架构

```
┌─────────────────────────────────────────────────────────────┐
│  交互层 (TUI)                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Textual 框架                                         │  │
│  │  - ChatArea: 对话区域（Markdown 渲染、流式显示）      │  │
│  │  - InputBox: 输入框（历史命令、命令补全）             │  │
│  │  - StatusBar: 状态栏（模型、Token、时长）             │  │
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
| StatusBar | `tui/widgets/status_bar.py` | 状态栏，显示模型、Token、会话时长等信息 |
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

#### 3. 工具层 (Tools) - 待实现

- 文件读写工具
- 命令执行工具
- 代码搜索工具
- Git 操作工具

#### 4. 记忆层 (Memory) - 待实现

- 项目上下文管理
- 对话历史索引
- 用户偏好存储

#### 5. 安全层 (Security) - 待实现

- 命令确认机制
- 文件 diff 预览
- 操作回滚
- 沙箱执行

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
│       │   ├── conversation.py # 会话管理
│       │   ├── models/
│       │   │   ├── client.py   # LLM 客户端接口
│       │   │   └── message.py  # 消息数据模型
│       │   └── adapters/
│       │       ├── factory.py  # 适配器工厂
│       │       ├── openai_adapter.py
│       │       ├── claude_adapter.py
│       │       ├── ollama_adapter.py
│       │       └── custom_adapter.py
│       └── tui/
│           ├── app.py          # TUI 主应用
│           └── widgets/
│               ├── chat_area.py
│               ├── input_box.py
│               └── status_bar.py
└── tests/
    └── test_e2e.py
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
pip install textual httpx pyyaml rich
```

### 启动 MewCode

```powershell
cd E:\agent_class\project
.\start.ps1
```

### 配置 API

编辑 `config.yaml` 文件，配置你的 API 密钥：

```yaml
llm:
  default_model: "mimo-v2.5-pro"
  default_provider: "custom"

  models:
    mimo-v2.5-pro:
      provider: "custom"
      base_url: "https://your-api-endpoint.com/v1"
      api_key: "your-api-key"
      api_format: "openai"
      model: "mimo-v2.5-pro"
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
| `/quit` | 退出程序 |

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Enter` | 发送消息 |
| `Ctrl+C` | 退出程序 |
| `Ctrl+S` | 保存会话 |
| `Ctrl+Shift+C` | 复制最后一条 AI 回复 |
| `↑` / `↓` | 浏览历史命令 |
| `Tab` | 命令补全 |

---

## 版本历史

- **v0.0** - 初始版本
  - 多 LLM 支持（OpenAI、Claude、Ollama、自定义端点）
  - 流式对话
  - Markdown 渲染
  - 会话持久化
  - TUI 界面

---

## 许可证

MIT License
