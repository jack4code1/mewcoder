# CHANGELOG

本文件记录版本变更，供 coding agent 快速了解项目演进和代码修改范围。

---

## V0.2 — 2026-06-06 — Claude

### 清理临时文件与过时文档

- 删除 7 个 `__pycache__/` 目录（Python 字节码缓存）
- 删除 `.pytest_cache/`（pytest 缓存）
- 删除 `PROGRESS.md`（与 CHANGELOG.md / CLAUDE.md 内容重叠且已过时）

### 修复硬编码 API Key，接入 config.yaml

**问题**：`app.py:204` 把 API Key 和 base_url 直接写死在代码里，`config.yaml` 从未被读取，换模型时无法自动获取对应配置。

**方案**：新增 `config.py` 配置加载模块，`app.py` 启动时读取 `config.yaml`，创建 LLM 客户端时从配置中取 api_key、base_url、api_format。

**修改文件**：

- `src/mewcode/config.py`（新增）
  - `load_config()` — 加载 `config.yaml`，返回 dict
  - `get_model_config(config, model)` — 从配置中取指定模型的参数
- `src/mewcode/tui/app.py`
  - 新增 `from ..config import get_model_config, load_config`
  - `__init__()` — 加载配置，从 `config.llm.default_model` / `default_provider` 读默认值，CLI 参数优先
  - `_process_with_llm()` — 用 `get_model_config()` 取 api_key/base_url/api_format，移除硬编码值

### 修复自定义消息类未继承 Textual Message

**问题**：`InputSubmitted`、`TabPressed`、`ShowCommands` 是普通 class，不是 `textual.message.Message` 子类。Textual 的 `post_message()` 要求消息继承 `Message`，当前写法可能导致事件分发异常。

**方案**：三个消息类改为继承 `textual.message.Message`，`__init__` 调用 `super().__init__()`。

**修改文件**：

- `src/mewcode/tui/widgets/input_box.py`
  - 新增 `from textual.message import Message`
  - `InputSubmitted(Message)`、`TabPressed(Message)`、`ShowCommands(Message)` — 继承 Message 并调用 super

### 同步命令补全列表

**问题**：`input_box.py` 的补全列表是 `/help, /clear, /save, /model, /quit, /history`，与 `app.py` 实际支持的命令不一致（缺 `/copy`、`/mode`，多 `/history`）。

**方案**：补全列表改为 `/help, /copy, /clear, /save, /model, /mode, /quit`。

**修改文件**：

- `src/mewcode/tui/widgets/input_box.py`
  - `_complete_command()` — 更新 commands 列表

### 退出时清理 LLM 客户端

**问题**：`LLMClient` 内部持有 `httpx.AsyncClient`，app 退出时没有调用 `close()`，连接不会被正确释放。

**方案**：在 `MewCodeApp` 中添加 `on_unmount()` 生命周期钩子，关闭 LLM 客户端。

**修改文件**：

- `src/mewcode/tui/app.py`
  - 新增 `on_unmount()` — 调用 `self.llm_client.close()` 释放连接

---

## V0.1 — 2026-06-06 — Claude

### 对话区域文本选择与复制

**问题**：对话区域使用 `RichLog` 控件，不支持鼠标选择和复制文本。

**方案**：将 `RichLog` 替换为 `ScrollableContainer` + 多个 `Static` 控件，每条消息为独立 `Static`，支持原生文本选择。

**修改文件**：

- `src/mewcode/tui/widgets/chat_area.py`
  - 移除 `RichLog`，改用 `ScrollableContainer`（id=`chat-scroll`）作为消息容器
  - 每条消息（用户/AI/系统）各生成一个 `Static` 控件并 `mount()` 到容器
  - 新增 `_render_to_text()`：用 `Rich Console.capture()` 将 Markdown 等 renderable 转为 `Text` 对象，解决 `Static` 对 Rich renderable 不支持选择的问题
  - 流式输出：`add_stream_chunk()` 仍通过 `update()` 实时刷新当前流式控件
  - 流式结束：`add_assistant_message_end()` 移除被 `update()` 污染的旧控件，`mount()` 全新 `Static`，确保文本可选
- `src/mewcode/tui/app.py`
  - CSS 移除 `RichLog` 规则，新增 `#chat-scroll`、`.chat-msg` 样式

### `/copy` 命令与快捷键

**问题**：即使文本可选，鼠标操作不便，需要快捷方式复制 AI 回复。

**方案**：新增 `/copy` 命令和 `Ctrl+Shift+C` 快捷键，将最后一条 AI 回复写入系统剪贴板。

**修改文件**：

- `src/mewcode/tui/app.py`
  - 新增 `_copy_last_reply()` 方法：从 `chat_area._messages` 取最后一条 assistant 消息，调用 `self.copy_to_clipboard()`
  - `_handle_command()` 新增 `/copy` 分支
  - `BINDINGS` 新增 `ctrl+shift+c` 绑定
  - 新增 `action_copy_last_reply()` action 方法
  - `/help` 输出新增 `/copy` 说明
- `MANUAL.md` — 内置命令表和快捷键表新增 `/copy` 和 `Ctrl+Shift+C`

---

## V0.0 — 初始版本 — opencode

项目创建，包含以下模块：

- **engine/models** — `Message`、`MessageRole`、`TokenUsage`、`LLMResponse`、`StreamChunk` 数据模型；`LLMClient` 抽象基类
- **engine/adapters** — `OpenAIAdapter`、`ClaudeAdapter`、`OllamaAdapter`、`CustomAdapter` 适配器；`AdapterFactory` 工厂
- **engine/conversation** — `Conversation`、`ConversationManager` 会话管理与 YAML 持久化
- **tui** — 基于 Textual 的 TUI 界面：`MewCodeApp`、`ChatArea`（RichLog）、`InputBox`、`StatusBar`
- **tests** — pytest 测试（ConversationManager、AdapterFactory、Message 序列化）
- **配置** — `config.yaml`（LLM 模型/会话/TUI 配置）、`pyproject.toml`
