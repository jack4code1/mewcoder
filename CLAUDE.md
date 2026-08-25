# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MewCode is a terminal AI coding assistant built in Python, similar to Claude Code. It supports multiple LLM providers (OpenAI, Claude, Ollama, custom endpoints) with streaming responses rendered in a TUI built on Textual.

## Development Commands

### Install Dependencies
```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

### Run the Application
```bash
mewcode
# Or
python -m mewcode
```

### Run Tests
```bash
python -m pytest
```

### Run a Single Test
```bash
python -m pytest tests/test_e2e.py::TestAdapterFactory::test_detect_provider_openai -v
```

## Architecture

The project follows a layered architecture defined in `spec.md`:

```
src/mewcode/
├── main.py              # Entry point, delegates to cli.py
├── cli.py               # CLI argument parsing
├── config.py            # load_config(), get_model_config() — reads config.yaml
├── logger.py            # Logging configuration
├── engine/              # Core engine layer
│   ├── models/
│   │   ├── message.py   # Data models: Message, MessageRole, TokenUsage, LLMResponse, StreamChunk
│   │   └── client.py    # LLMClient abstract base class (chat, chat_stream, validate_connection)
│   ├── adapters/        # LLM provider adapters (Strategy pattern)
│   │   ├── factory.py   # AdapterFactory - creates clients by model/provider name
│   │   ├── openai_adapter.py
│   │   ├── claude_adapter.py
│   │   ├── ollama_adapter.py
│   │   └── custom_adapter.py  # Generic OpenAI-compatible endpoint adapter
│   ├── conversation.py  # Conversation + ConversationManager (YAML persistence)
│   ├── context/         # Token budgeting, context planning, project memory
│   ├── security/        # Optional approval, policy, and audit gateway
│   ├── mcp/             # Foundation-only MCP adapters and configuration
│   ├── extensions/      # Foundation-only commands, skills, and hooks
│   └── orchestration/   # Foundation-only task, team, and worktree primitives
└── tui/                 # Textual TUI layer
    ├── app.py           # MewCodeApp (main Textual App), run_app() entry
    └── widgets/
        ├── chat_area.py    # Chat display: ScrollableContainer + Static widgets, streaming + Markdown
        ├── input_box.py    # Input widget with history, command completion, Tab optimization
        └── status_bar.py   # Bottom status bar (model, tokens, duration, mode)
```

### Key Design Patterns

- **Adapter Pattern**: All LLM providers implement `LLMClient` abstract base class from `engine/models/client.py`. To add a new provider, create an adapter in `engine/adapters/` inheriting `LLMClient` and register it in `AdapterFactory.PROVIDERS`.
- **Factory Pattern**: `AdapterFactory` auto-detects provider from model name (e.g., `gpt-4` → openai, `claude-3-5-sonnet` → claude) and creates the appropriate client.
- **CustomAdapter**: Handles any OpenAI-compatible API endpoint. Supports `reasoning_content` field (used by some models like MiMo) as fallback when `content` is empty.
- **Conversation persistence**: Serialized to YAML in `~/.mewcode/sessions/`. Uses `ConversationManager` for multi-session management.

### TUI Flow

1. `MewCodeApp` composes: Header → Vertical(ChatArea, StatusBar, InputBox) → Footer
2. User submits message via `InputSubmitted` event → `_handle_message()` or `_handle_command()`
3. LLM processing runs in a Textual worker (`run_worker`) with `exclusive=True`
4. Streaming: `chat_stream()` yields `StreamChunk` objects → `ChatArea.add_stream_chunk()` appends to a buffer → flushed as Markdown via Rich

### Configuration

Runtime config is in `config.yaml` at project root. Defines LLM models, session storage dir (`~/.mewcode/sessions`), and TUI display options. The default model is `mimo-v2.5-pro` using a custom endpoint.

### Test Framework

Tests use pytest with `asyncio_mode = "auto"` (configured in `pyproject.toml`). Test files are in `tests/` and cover adapters, agent loops, tools, security, context planning, metrics, and TUI behavior.

### Capability Status

- Project context budgeting, project memory commands, and optional security approvals are integrated into the TUI.
- MCP, Skills, Hooks, task orchestration, Worktrees, and Agent Teams currently provide foundation modules only; do not describe them as complete user workflows.

## Development Workflow

**HARD RULE — 强制流程：** 对本项目的任何修改（新增功能、修改模块、修复 Bug、调整配置、重构代码、修改文档结构等），都必须先调用 `mew-spec` skill,按其规定的四阶段流程执行：

```
spec.md（做什么）→ plan.md（怎么做）→ task.md（按什么顺序做）→ checklist.md（做对了没）
```

**触发条件（满足任意一条就必须调用 mew-spec）：**
- 用户要求「修改」「新增」「实现」「重构」「优化」「修复」项目中的任何代码或文档
- 用户提出一个新功能、新模块、新章节
- 用户描述一个想法,即使看起来很小很简单
- 用户说「帮我做 X」「加一个 Y」「改一下 Z」

**禁止行为：**
- 在四份文档（spec.md / plan.md / task.md / checklist.md）全部生成并通过用户审批之前,禁止编写任何实现代码
- 禁止以「这个太简单」「这个很明显」「直接改一行就行」为理由跳过流程
- 禁止合并步骤、跳过审批、自由发挥
- 禁止在没有获得用户对当前阶段文档的明确批准时,推进到下一阶段

**唯一例外：** 纯查询/解释/阅读操作(例如「这段代码是什么意思」「这个函数在哪里」「跑一下测试看看」)不触发流程。一旦涉及修改文件,立即进入流程。

**调用方式：** 每次新会话首次出现修改类需求时,主动调用 `mew-spec` skill,然后严格遵循其指引(一次问一个问题、逐段呈现、逐阶段审批、先有证据再下结论)。

---

### 文档约定

- **spec.md**: Product spec (what/why, no implementation details)
- **plan.md**: Architecture, interfaces, data structures, technical decisions
- **task.md**: Task breakdown with file impacts, steps, and verification
- **checklist.md**: Observable acceptance criteria
- **CHANGELOG.md**: Version history with code change descriptions (written for coding agents)

完成开发和验收后,同步更新 CHANGELOG.md。
