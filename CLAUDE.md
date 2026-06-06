# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MewCode is a terminal AI coding assistant built in Python, similar to Claude Code. It supports multiple LLM providers (OpenAI, Claude, Ollama, custom endpoints) with streaming responses rendered in a TUI built on Textual.

## Development Commands

### Install Dependencies
```bash
pip install textual httpx pyyaml rich
pip install pytest pytest-asyncio  # dev only
```

### Run the Application
```powershell
# Windows (recommended)
.\start.ps1

# Or manually
$env:PYTHONPATH="E:\agent_class\project\src"
python -c "from mewcode.tui.app import run_app; run_app(model='mimo-v2.5-pro', provider='custom')"
```

### Run Tests
```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/ -v
```

### Run a Single Test
```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
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
│   └── conversation.py  # Conversation + ConversationManager (YAML persistence)
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

1. `MewCodeApp` composes: Header → Vertical(ChatArea, InputBox) → StatusBar → Footer
2. User submits message via `InputSubmitted` event → `_handle_message()` or `_handle_command()`
3. LLM processing runs in a Textual worker (`run_worker`) with `exclusive=True`
4. Streaming: `chat_stream()` yields `StreamChunk` objects → `ChatArea.add_stream_chunk()` appends to a buffer → flushed as Markdown via Rich

### Configuration

Runtime config is in `config.yaml` at project root. Defines LLM models, session storage dir (`~/.mewcode/sessions`), and TUI display options. The default model is `mimo-v2.5-pro` using a custom endpoint.

### Test Framework

Tests use pytest with `asyncio_mode = "auto"` (configured in `pyproject.toml`). Test files are in `tests/`. The test suite covers `ConversationManager`, `AdapterFactory`, and `Message` data model serialization.

## Development Workflow

Per `AGENTS.md`, the project uses a three-document spec-driven workflow:
- **spec.md**: Product spec (what/why, no implementation details)
- **tasks.md**: Task breakdown with file impacts and dependencies
- **checklist.md**: Observable acceptance criteria per task
- **CHANGELOG.md**: Version history with code change descriptions (written for coding agents)

When adding features, update all three documents and CHANGELOG.md alongside code changes.
