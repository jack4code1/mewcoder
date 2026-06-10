# CHANGELOG

## V0.6 - 2026-06-10 - Codex

### Token metrics and status bar - 05-token-metrics

Implemented the approved `specs/05-token-metrics/` plan.

- Added engine metrics models for per-call API metrics and session aggregates.
- Added Agent Loop timing for TTFT, total latency, and average output speed in `tok/s`.
- Kept token usage unavailable as `N/A` instead of displaying fake zero values.
- Added OpenAI-compatible streaming usage requests with `stream_options.include_usage`.
- Normalized streaming usage for OpenAI, Custom, Claude, and Ollama adapters.
- Persisted message-level `token_usage` and aggregate `api_metrics` to session YAML.
- Updated the TUI status bar to show real token totals, prompt/completion split, average `tok/s`, TTFT, and latency.
- Added compact status bar formatting for narrow terminal widths.
- Added tests for metrics math, event payloads, Agent Loop timing, adapter usage parsing, persistence, status bar formatting, and TUI integration.

本文件记录版本变更，供 coding agent 快速了解项目演进和代码修改范围。

---

## V0.5 — 2026-06-10 — Codex

### Agent Loop 多步循环 — 04-agent-loop 章节

基于 `specs/04-agent-loop/` 四份文档实现 ReAct Agent Loop,将原先 TUI 内的单步工具调用流程升级为引擎层多轮循环。范围包含 AgentEvent 事件流、停止条件、工具分批执行、TUI 事件消费,以及两个输入框交互 BUG 修复。

**新增章节文档** — `specs/04-agent-loop/`

- `spec.md` — Agent Loop 能力边界、停止条件、事件流、TUI 输入回归修复范围
- `plan.md` — 引擎层 Agent Loop、AgentEvent、工具分批、取消和 TUI 接入设计
- `task.md` — 10 个任务,覆盖事件模型、循环、停止条件、批处理、TUI 接入、输入框修复和验证
- `checklist.md` — 可观测验收项,含 50 轮上限、3 次无效工具终止、Esc 取消、Enter 清空、Up/Down 历史

**新增模块**

- `src/mewcode/engine/agent_events.py`
  - 定义 `AgentEventType`,覆盖 `stream_text` / `tool_use` / `tool_result` / `turn_complete` / `loop_complete` / `usage` / `error`
  - 定义 `AgentStopReason`,覆盖模型自然完成、最大迭代、用户取消、重复无效工具和不可恢复错误
  - 提供 `AgentEvent` 工厂方法,让 UI 和测试按事件类型消费 payload
- `src/mewcode/engine/agent.py`
  - 新增 `run_agent_loop(...)` async generator
  - 模型无工具调用时自然结束
  - 模型有工具调用时持久化 assistant 消息、执行工具、持久化 tool result,再进入下一轮
  - assistant 文本和 tool_calls 保持在同一条 assistant message
  - tool result 保留原始 `tool_call_id`
  - 支持最大 50 轮迭代、取消事件、连续 3 次 unknown/disabled tool 终止
  - 支持按 `is_concurrency_safe` 将工具调用分成并发批和串行批

**TUI 接入**

- `src/mewcode/tui/app.py`
  - `_process_with_llm` 改为消费 AgentEvent,不再直接控制单步工具流程
  - 删除第二轮 tool_calls 忽略逻辑,模型可继续多轮调用工具
  - `stream_text` 更新当前 assistant 流式消息
  - `tool_use` / `tool_result` 驱动工具 trace 的 pending / success / error 状态
  - `usage` 更新状态栏 token 显示
  - `loop_complete` 统一恢复 Idle
  - 新增 `Esc` 取消当前 Agent Loop,保留 `Ctrl+C` 退出应用

**输入框 BUG 修复**

- `src/mewcode/tui/widgets/input_box.py`
  - 显式处理子 `Input` 的 Enter submit 事件,提交后立即清空输入栏
  - 显式处理 Up / Down 按键,支持在已提交提示词之间快速切换
  - 空输入不会加入历史
  - Down 从最新历史项回到空输入

**测试**

- `tests/test_agent_events.py` — 覆盖 AgentEvent payload
- `tests/test_agent_loop.py` — 覆盖纯聊天结束、多轮工具循环、连续无效工具终止、最大迭代、取消、工具分批
- `tests/test_input_box.py` — 覆盖 Enter 清空、空输入不入历史、Up/Down 历史导航
- `tests/test_tui_agent_loop.py` — 覆盖 TUI 消费 Agent Loop 多轮工具事件
- `tests/test_tui_tool_flow.py`
  - 原“第二次 tool_calls 忽略”回归改为“第二次 tool_calls 继续循环”

**文档**

- `README.md` / `MANUAL.md`
  - 更新工具流程为 Agent Loop 多步循环
  - 增加 `Esc` 取消当前循环
  - 明确 `Enter` 提交后清空输入栏、`↑` / `↓` 浏览历史提示词
- `.gitignore`
  - 忽略测试运行目录 `.tmp_pytest/` 和 `.mewcode_test_sessions/`

**运行验证**

- `python -m pytest tests/test_agent_events.py tests/test_agent_loop.py tests/test_input_box.py -v -p no:cacheprovider` → 13 passed
- `python -m pytest tests/test_tui_agent_loop.py tests/test_tui_tool_flow.py tests/test_tui_tool_trace.py tests/test_input_box.py -v -p no:cacheprovider` → 12 passed
- `python -m pytest tests/test_message_tool_calls.py tests/test_adapter_tool_calls.py tests/test_adapter_anthropic_tool_use.py -v -p no:cacheprovider` → 38 passed
- `rg "single-step gate|single-step tool flow" src\mewcode` → no output
- `TMP=.tmp_pytest TEMP=.tmp_pytest python -m pytest tests/ -v -p no:cacheprovider` → 164 passed

**环境说明**

- 当前 Windows 用户 Temp 目录不可写,直接运行全量测试会在 `tmp_path` fixture 创建阶段失败。将 `TMP` / `TEMP` 指向工作区内 `.tmp_pytest` 后全量测试通过。

---

## V0.4 — 2026-06-10 — Codex

### 工具系统验收加固 — 03-tools-hardening 章节

基于 `specs/02-tools/checklist.md` 的验收结果,补齐配置安全、自动化验收和 checklist 分类能力。保留明文 API Key 配置方式,新增环境变量优先读取。

**新增章节文档** — `specs/03-tools-hardening/`

- `spec.md` — 明确本章只做工具系统验收修正与测试增强,不引入 Agent Loop、权限系统或新工具
- `plan.md` — 设计 `api_key_env` 环境变量优先、明文 `api_key` fallback 的配置解析方案
- `task.md` — 10 个任务,覆盖配置解析、文档、语言扫描、TUI 测试、payload 测试、验收与 changelog
- `checklist.md` — 分成 Automated Checks / Static Scans / Config Integration / Manual TUI Checks / Real API Checks / Final Regression

**配置解析**

- `src/mewcode/config.py`
  - `get_model_config()` 返回模型配置副本,避免调用方意外改动原始配置
  - 支持可选 `api_key_env`:当指定环境变量存在且非空时,返回配置中的 `api_key` 使用环境变量值
  - 环境变量缺失或为空时,继续使用现有明文 `api_key`
- `config.yaml`
  - 默认自定义模型增加 `api_key_env: "MIMO_API_KEY"`
  - 保留现有 `api_key` 明文 fallback

**文档**

- `README.md` / `MANUAL.md`
  - 配置示例新增 `api_key_env`
  - 说明环境变量优先、明文 `api_key` 作为 fallback
  - 示例只使用 placeholder,不公开真实密钥

**语言策略修正**

- `src/mewcode/engine/tools/system_prompt.py`
  - 移除工具实现目录中的中文 docstring 命中
  - 保持运行时 system prompt 和工具描述为英文

**新增测试**

- `tests/test_config_env.py` — 覆盖环境变量优先、明文 fallback、空环境值 fallback、配置不被 mutation
- `tests/test_tui_tool_trace.py` — 覆盖工具调用 trace 的 pending / success / error 三种显示状态
- `tests/test_tui_tool_flow.py` — 用 fake LLM client 覆盖 ReadFile 成功、ReadFile 失败、Bash、第二次 tool_calls 忽略、纯对话回归
- `tests/test_payload_language.py` — 覆盖 payload 中 system prompt、工具描述、metadata 不泄漏、模型可见字符串无中文

**已运行验证**

- `python -m pytest tests/test_config_env.py tests/test_tui_tool_trace.py tests/test_tui_tool_flow.py tests/test_payload_language.py -v` → 17 passed
- `python -m pytest tests/ -v` → 150 passed
- `rg "[\p{Han}]" src\mewcode\engine\tools` → no output
- `rg "api_key_env" config.yaml README.md MANUAL.md` → all three files matched
- `rg "tp-" README.md MANUAL.md tests` → no output

---

## V0.3 — 2026-06-09 — Claude

### 工具系统(单步) — 02-tools 章节

让模型可以请求工具、本地执行、把结果回灌后再给最终回复。覆盖单步:模型 → 工具 → 模型。多步 Agent Loop 留给后续章节。

**新增模块** — `src/mewcode/engine/tools/`(全新目录)

- `base.py` — `Tool` 抽象基类、`ToolResult`、`ToolContext`(含 `resolve_path` 和 `detect`)、`ToolError` 哨兵异常
- `registry.py` — `ToolRegistry`,提供 `register` / `enable("all" | "readonly" | list)` / `get` / `list_enabled` / `to_openai_format` / `to_anthropic_format` / `async execute`(含错误兜底:可恢复错误转 `ToolResult(is_error=True)`,`ToolError` 上抛)
- `read_file.py` — `ReadFileTool`,带行号读取,支持 offset/limit,二进制检测拒读
- `write_file.py` — `WriteFileTool`,递归创建父目录,覆盖写入
- `edit_file.py` — `EditFileTool`,旧片段必须唯一匹配,改完返回 ±5 行预览
- `bash.py` — `BashTool`,默认 30s 超时,输出 >10000 字符截断为前 2000 + 后 8000,非零退出码不算错误,只有超时算错误
- `glob.py` — `GlobTool`,递归 glob,排除噪音目录(`.git` / `node_modules` / `__pycache__` / `.venv` 等),mtime 倒序,200 上限
- `grep.py` — `GrepTool`,正则检索,跳过二进制,支持 `include` glob 与上下文行,100 命中上限
- `system_prompt.py` — `build_system_prompt(ctx, registry)`,英文 system prompt(cwd / OS / 工具使用原则 / 中文回复指令)
- `__init__.py` — `build_default_registry(ctx, config)` 工厂,注册全部 6 工具并按 `config["tools"]["enabled"]` 启用

**扩展** — `engine/models/`

- `message.py`
  - 新增 `@dataclass ToolCall`(`id` / `name` / `input: dict` / `parse_error: Optional[str]`)
  - `Message` 增加可选字段 `tool_calls` / `tool_call_id` / `tool_result_is_error`(默认 None)
  - `to_dict` 仅在字段非空时输出新字段;`from_dict` 用 `.get()` 读取 → 老 session 文件加载零变动
  - `StreamChunk` 增加可选字段 `tool_calls`,流式末尾携带聚合好的工具调用
  - `LLMResponse` 增加可选 `tool_calls` 字段
- `client.py` — `chat` / `chat_stream` 抽象签名增加 `tools: Optional[list[dict]] = None` 参数
- `__init__.py` — 公开导出 `ToolCall`

**扩展** — `engine/adapters/`

- `_openai_protocol.py`(新增) — OpenAI 协议族共享 helper:
  - `convert_messages_to_openai(messages)` — 把项目中性 Message 翻译成 OpenAI 线协议(assistant.tool_calls / role:tool 全支持)
  - `OpenAIToolCallAggregator` — 流式 `tool_calls` 增量聚合,按 `index` 累积 id/name/arguments,finalize 时尝试 `json.loads(arguments)`,失败设置 `parse_error`,不让流处理崩溃
- `custom_adapter.py` / `openai_adapter.py` / `ollama_adapter.py`
  - `_convert_messages` 改用 `convert_messages_to_openai` 统一处理
  - `chat` / `chat_stream` 接受 `tools` 参数,放进 payload
  - `chat_stream` 复用 `OpenAIToolCallAggregator`,在 finish_reason 时 yield 一个携带聚合 `tool_calls` 的最终 chunk
  - `OllamaAdapter` 额外处理 arguments 已是 dict 形态的情况
- `claude_adapter.py`
  - `_convert_messages` 重写:assistant 输出 `[text, tool_use, ...]` content blocks;**连续 TOOL 消息聚合为单条 user 消息含多个 tool_result blocks**(Anthropic 协议要求);system 抽出为顶层字段
  - `chat_stream` 解析 `content_block_start/delta/stop` + `message_delta`,聚合 `input_json_delta` 拼成完整 JSON,parse 失败时同样写 `parse_error`
  - `chat` 也提取 `tool_use` 块为 `ToolCall` 列表

**扩展** — `tui/`

- `widgets/chat_area.py`
  - `add_tool_call(name, params_summary)` — 渲染 `→ tool_name(summary)` 行,返回 widget id
  - `update_tool_call_result(widget_id, success, summary)` — 更新为 `✓ tool_name(...): summary`(成功)或 `✗ ...`(失败)
  - **修复**:流式占位 widget 的 ID 从固定 `__streaming__` 改为每次 `streaming-<uuid>`,避免单步流程中两次 stream 紧挨发生时 `remove()` 异步未完导致的 ID 冲突
- `app.py`
  - `MewCodeApp.__init__` 锁定 `ToolContext`(working_dir = `os.getcwd()`),`build_default_registry` 注册 6 工具
  - `_build_tools_payload` 按 adapter 类型选 OpenAI 或 Anthropic 格式
  - `_messages_with_system` 每次请求前重新构造 system prompt(不持久化进 conversation)
  - `_process_with_llm` 重写为单步流程:第一次流式 → 收集 tool_calls → 写 assistant 消息 → 串行执行每个工具(parse_error 直接 isError) → 写 TOOL 消息 → 第二次流式给最终回复 → 第二次响应中的 tool_calls **忽略并打日志**(单步约束 AC17)
  - 跨平台 ToolContext 检测(Windows → cmd,Unix → sh)

**扩展** — 配置

- `config.py` — 新增 `get_tools_config(config)`,合并默认值
- `config.yaml` — 新增 `tools` 节点(`enabled: "all"`,`bash_timeout: 30`,`max_output_chars: 10000`)

**测试** — 新增 11 个测试文件,共 123 个 case

- `test_tools_base.py` — Tool / ToolResult / ToolContext 行为
- `test_tools_registry.py` — 注册、启用策略、双协议格式输出、调度执行的所有错误分支
- `test_tools_{read_file,write_file,edit_file,bash,glob,grep}.py` — 每个工具覆盖成功路径和所有错误分支(如 ReadFile 的二进制检测、EditFile 的多匹配、Bash 的超时与截断、Glob/Grep 的噪音目录排除与上限)
- `test_message_tool_calls.py` — `ToolCall` / `Message` 序列化、`Message` 向后兼容、`StreamChunk` 扩展
- `test_adapter_tool_calls.py` — OpenAI 协议族流式 tool_calls 聚合(用 fake httpx stream 注入预制 SSE),覆盖 CustomAdapter / OpenAIAdapter
- `test_adapter_anthropic_tool_use.py` — Anthropic 流式 content_block_start/delta/stop 聚合

**最终结果**:`pytest tests/ -v` 共 **133 passed**(原 10 case + 本章 123 case)

**章节文档** — `specs/02-tools/`

- `spec.md` — 18 条功能需求 + 11 条非功能需求 + 9 条「不做的事」+ 24 条验收标准
- `plan.md` — 架构 / 数据结构 / 模块设计 / 模块交互 / 文件组织 / 21 条技术决策
- `task.md` — 18 个任务,带文件清单、步骤、验证、依赖图
- `checklist.md` — 33 项验收(28 自动化 + 5 端到端场景)

**工作流支撑** — `.claude/skills/mew-spec/SKILL.md`

新增 mew-spec skill,把「需求澄清 → 设计 → 任务拆解 → 验收设计 → 开发 → 验收」六阶段流程沉淀成可复用 skill。`CLAUDE.md` 加入 HARD RULE,后续任何修改都强制走流程。

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
