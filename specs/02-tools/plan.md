# MewCode 工具系统(单步) Plan

## 架构概览

本章在现有「engine + tui」分层之上,引入第三个独立子系统 `engine/tools/`,并对 `engine/models`、`engine/adapters`、`engine/conversation`、`tui` 做最小侵入式扩展。

整体新增/修改一览(模块级):

- **engine/tools/**(全新)
  - `base.py` —— Tool 抽象基类、ToolResult、ToolContext、ToolError 异常类型
  - `registry.py` —— ToolRegistry,启用/禁用、按名查找、按协议输出工具描述
  - `read_file.py / write_file.py / edit_file.py / bash.py / glob.py / grep.py` —— 6 个内置工具
  - `system_prompt.py` —— 根据上下文构造英文 system prompt 段
  - `__init__.py` —— 暴露 build_default_registry(config, ctx) 工厂

- **engine/models/**(扩展)
  - `message.py` —— Message 增加 tool_calls / tool_call_id / tool_use_blocks 等可选字段;新增 ToolCall、ToolResultBlock 数据类;to_dict/from_dict 向后兼容
  - `client.py` —— chat/chat_stream 接口增加 tools 参数

- **engine/adapters/**(扩展)
  - `custom_adapter.py / openai_adapter.py / ollama_adapter.py` —— 接 OpenAI tool_calls 协议:_convert_messages 处理 tool_calls / role:tool;chat_stream 聚合 tool_calls 增量
  - `claude_adapter.py` —— 接 Anthropic content block 协议:_convert_messages 处理 content blocks;chat_stream 聚合 tool_use 块
  - `factory.py` —— 不动

- **engine/conversation.py**(无侵入)
  - 依赖 Message.to_dict/from_dict 自动具备工具调用历史持久化能力

- **tui/widgets/chat_area.py**(扩展)
  - 新增 add_tool_call(tool_name, params_summary) 和 update_tool_call_result(success, summary) 两个方法,渲染精简轨迹

- **tui/app.py**(修改)
  - `_process_with_llm` 改造为单步工具流程:第一次流式 → 检测到工具调用 → 调度 ToolRegistry 执行 → 把 tool_use / tool_result 追加到 conversation → 第二次流式拿最终回复
  - 启动时根据 config.yaml 的 `tools` 节点构造 ToolRegistry,并把 ToolContext(working_dir=os.getcwd()) 传入

- **config.py / config.yaml**(扩展)
  - 新增 `tools` 节点,字段 `enabled`(列表 / "all" / "readonly")、`bash_timeout`(默认 30)、`max_output_chars`(默认 10000)

## 协议适配策略

LLM 协议在 Adapter 内部翻译,上层只看到统一的 Message 模型。

- **OpenAI 协议族**(CustomAdapter / OpenAIAdapter / OllamaAdapter)
  - 工具描述:`tools=[{type:"function", function:{name, description, parameters}}]`
  - 模型请求:`assistant.message.tool_calls = [{id, type:"function", function:{name, arguments}}]`(arguments 是字符串化 JSON)
  - 工具结果:`{role:"tool", tool_call_id, content}`
  - 流式聚合:`choices[0].delta.tool_calls[i]` 携带 index / id / function.name / function.arguments(增量字符串),按 index 累积,finish_reason="tool_calls" 时收尾

- **Anthropic 协议**(ClaudeAdapter)
  - 工具描述:`tools=[{name, description, input_schema}]`
  - 模型请求:`assistant.content = [{type:"text", text}, {type:"tool_use", id, name, input}]`
  - 工具结果:`{role:"user", content:[{type:"tool_result", tool_use_id, content, is_error}]}`
  - 流式聚合:`content_block_start{type:"tool_use", id, name}` → `content_block_delta{type:"input_json_delta", partial_json}` → `content_block_stop`,期间累加 partial_json 字符串

上层(TUI、ConversationManager、ToolRegistry 调度循环)只与中性的 Message 形态打交道,不感知协议差异(N9 协议透明)。

## 核心数据结构

> 全部位于 `engine/tools/base.py` 和 `engine/models/message.py`,以下用类型描述,不写完整 Python 代码。

### ToolContext (engine/tools/base.py)

工具执行的运行上下文,在 MewCodeApp.on_mount 时锁定,然后由调度循环传给每次工具执行。

| 字段 | 类型 | 说明 |
|------|------|------|
| working_dir | Path | 启动时的 os.getcwd(),所有相对路径以此为根 |
| os_name | str | 'windows' / 'darwin' / 'linux' |
| platform_shell | str | 'cmd' / 'powershell' / 'sh',Bash 工具用 |

### ToolResult (engine/tools/base.py)

工具执行返回值,所有工具的 execute 都返回它(包括失败情况)。

| 字段 | 类型 | 说明 |
|------|------|------|
| content | str | 给模型看的英文文本(成功时是结果,失败时是错误说明) |
| is_error | bool | 是否错误结果(进协议时映射到 OpenAI tool 消息的语义错误前缀 / Anthropic tool_result 的 is_error 字段) |
| metadata | dict | 给 UI 用的元信息(如 file_path、command、duration_ms),不进入 LLM 上下文 |

### ToolError (engine/tools/base.py)

仅用于真正的系统级故障(OOM 等),会被向上抛。可恢复错误绝不抛此异常,而是包成 ToolResult(is_error=True)。

### Tool (engine/tools/base.py,抽象基类)

| 方法/属性 | 签名 | 说明 |
|-----------|------|------|
| name | str(类属性) | 工具名(英文,符合 [a-zA-Z_][a-zA-Z0-9_]* ) |
| description | str(类属性) | 英文描述,包含「做什么/何时用/何时不用/参数约束/返回格式/与其他工具配合」 |
| input_schema | dict(类属性) | JSON Schema,手写 dict |
| category | Literal['file','shell','search'] (类属性) | 分类 |
| is_read_only | bool(类属性) | 是否只读 |
| is_destructive | bool(类属性) | 是否破坏性 |
| is_concurrency_safe | bool(类属性) | 默认 False,只读工具(ReadFile/Glob/Grep)为 True |
| validate_input(input: dict) -> Optional[str] | 实例方法 | 返回错误说明字符串(英文)或 None。schema 之外的语义校验放这里 |
| async execute(ctx: ToolContext, input: dict) -> ToolResult | 实例方法,抽象 | 执行工具 |

子类化即可定义新工具,不强制工厂函数模式。

### ToolRegistry (engine/tools/registry.py)

| 方法 | 签名 | 说明 |
|------|------|------|
| register(tool: Tool) | None | 注册工具,重名抛 ValueError |
| get(name: str) | Optional[Tool] | 按名查找 |
| list_enabled() | list[Tool] | 当前启用的工具 |
| to_openai_format() | list[dict] | 输出 OpenAI tools 参数:[{type:"function", function:{name, description, parameters}}] |
| to_anthropic_format() | list[dict] | 输出 Anthropic tools 参数:[{name, description, input_schema}] |
| async execute(ctx, name, input) -> ToolResult | 调度执行,处理找不到工具/参数校验失败/异常包装 |

### Message 扩展 (engine/models/message.py)

新增数据结构:

**ToolCall** —— 模型请求的一次工具调用(协议中性形态)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 工具调用 id(OpenAI 协议为 call id,Anthropic 为 tool_use id) |
| name | str | 工具名 |
| input | dict | 解析后的输入参数(注意是 dict 不是字符串,序列化时再字符串化) |
| parse_error | Optional[str] | 流式聚合 partial_json 解析失败时填,Adapter 用它生成 isError 的工具结果 |

**Message 字段扩展(全部可选,默认 None / 空)**

| 新增字段 | 类型 | 说明 |
|---------|------|------|
| tool_calls | Optional[list[ToolCall]] | assistant 消息携带,模型请求工具时填 |
| tool_call_id | Optional[str] | tool 角色消息携带,对应被回应的 ToolCall.id |
| tool_result_is_error | Optional[bool] | tool 角色消息携带 |

`role: TOOL` 已在现有枚举中,直接复用。

### 协议形态在 Adapter 边界翻译

Message 模型对外部呈现为「中性 OpenAI 风格」(content + tool_calls + tool_call_id),Adapter 在 _convert_messages 中按目标协议翻译:

- OpenAI 协议族:Message → 直接映射(role + content + tool_calls + tool_call_id)
- Anthropic 协议:assistant.tool_calls → content blocks 数组;tool 角色消息 → user 消息 + tool_result block

这样 ConversationManager 不需要知道两种协议形态。已有 session 文件加载时,新字段缺失按 None / 空处理(N3 向后兼容)。

### Message.to_dict / from_dict 兼容策略

- to_dict 输出:仅当 tool_calls / tool_call_id / tool_result_is_error 非空时才写入对应字段
- from_dict 解析:对新字段使用 .get(...) 读取,缺失返回默认值
- 老 session(纯 role+content)反序列化得到 Message,新字段全部为 None,行为与上一版完全一致(N2)

## 模块设计

### engine/tools/base.py

**职责:** 提供 Tool 抽象、ToolResult / ToolContext / ToolError 数据类型。无业务逻辑。

**对外接口:**
- `class Tool(ABC)` —— 见数据结构章节
- `@dataclass class ToolResult` —— content / is_error / metadata
- `@dataclass class ToolContext` —— working_dir / os_name / platform_shell;提供 `resolve_path(p: str) -> Path`,绝对路径直接返回,相对路径基于 working_dir
- `class ToolError(Exception)` —— 系统级错误

**依赖:** stdlib only(pathlib、abc、dataclasses、enum、platform)

### engine/tools/registry.py

**职责:** 集中管理工具,根据 config 决定哪些启用,提供两种协议的工具描述输出和执行调度。

**对外接口:**
- `class ToolRegistry`
  - `__init__(self, ctx: ToolContext)` —— 持有 ToolContext
  - `register(tool: Tool)` —— 启动期使用
  - `enable(names: list[str] | "all" | "readonly")` —— 启用策略
  - `get(name) / list_enabled() / to_openai_format() / to_anthropic_format()`
  - `async execute(name: str, input: dict) -> ToolResult` —— 找不到工具 / validate_input 失败 / execute 抛异常,统一包装成 ToolResult(is_error=True)

**依赖:** base.py、logger

### engine/tools/{read_file,write_file,edit_file,bash,glob,grep}.py

每个文件一个 Tool 子类,职责对应 spec F6-F11。共同模式:

- `name`、`description`(英文,内含「何时用 / 何时不用」)、`input_schema`(手写 dict)、元信息位列在类属性
- `validate_input` 做语义校验(路径必填、超时范围、glob 模式合法等),返回英文错误字符串
- `execute` 内部 try/except,把所有可恢复错误包成 ToolResult(is_error=True)

**依赖:** base.py;Bash 用 asyncio.subprocess;Grep/Glob 用 pathlib + re + fnmatch;ReadFile/WriteFile/EditFile 用 stdlib io。

**特殊点:**
- ReadFile:读前 512 字节判二进制(含 `\x00`),拒绝
- EditFile:读全文 → count 出现次数 → 0/多于 1 都返回错误 → str.replace 一次 → 写回 → 返回修改位置 ±5 行预览
- Bash:asyncio.create_subprocess_shell + wait_for(timeout) + 输出截断;Windows 走 cmd / powershell,Unix 走 sh,从 ToolContext 取
- Glob:用 pathlib.Path.glob,**模式经过 fnmatch.translate 转 regex 用于过滤;遍历时显式跳过 EXCLUDE_DIRS
- Grep:遍历指定根下所有文件,对每个非二进制文件逐行 re.search;-A/-B 上下文用环形缓冲;100 命中即停

### engine/tools/system_prompt.py

**职责:** 根据 ToolContext 和 ToolRegistry 构造英文 system prompt 段(F18)。

**对外接口:**
- `build_system_prompt(ctx: ToolContext, registry: ToolRegistry) -> str`

输出形如:

> You are MewCode, a coding assistant. The current working directory is `<working_dir>`. The host OS is `<os_name>`. You have access to file/shell/search tools. Prefer Grep/Glob to locate code before reading; for EditFile, include enough surrounding context in old_string to make it unique within the file. ...

具体内容 4-8 行,不重复 tools 参数已经携带的信息。

**依赖:** base.py、registry.py

### engine/tools/__init__.py

**对外接口:**
- `build_default_registry(ctx: ToolContext, config: dict) -> ToolRegistry`
  - 读 config["tools"]
  - 注册全部 6 个工具
  - 按 enabled 策略调用 registry.enable(...)

### engine/models/message.py(扩展)

**职责:** 在 Message 基础上承载工具调用与结果,保持向后兼容。

**对外接口变化:**
- 新增 `@dataclass class ToolCall`
- Message 增加可选字段 tool_calls / tool_call_id / tool_result_is_error
- to_dict / from_dict 处理新字段(可选输出、默认空读取)

**依赖:** stdlib only

### engine/models/client.py(扩展)

**职责:** 抽象基类增加 tools 参数。

**对外接口变化:**
- `chat(messages, tools: Optional[list[dict]] = None, **kwargs)` —— tools 是已经按目标协议格式化好的列表(Adapter 在调用前用 ToolRegistry.to_*_format() 准备)
- `chat_stream(messages, tools=None, **kwargs)` —— 同上

为最小侵入,tools 在调用方层面决定形态(由 Adapter 自身的 to_*_format 选择)。MewCodeApp 不直接构造 tools 列表,而是把 ToolRegistry 实例传给 LLM 调用层,由调用层统一处理。

### engine/adapters/custom_adapter.py / openai_adapter.py / ollama_adapter.py(扩展)

**职责:** 在原有流式逐 chunk 处理基础上,新增 tool_calls 增量聚合。

**主要改动:**
- `_convert_messages`:支持 assistant 消息的 tool_calls 字段输出、tool 角色消息(role:"tool", tool_call_id, content)输出
- `chat / chat_stream`:接受 tools 参数,直接放进 payload
- `chat_stream` 新增解析逻辑:
  - 维护 `tool_calls_buf: dict[int, {id, name, arguments_str}]`(按 index 累积)
  - 收到 `delta.tool_calls[i]` 时按 index 合并 id / function.name / function.arguments(arguments 是字符串增量)
  - finish_reason in {"tool_calls", "stop"} 且 buf 非空时,逐个尝试 json.loads(arguments_str),成功 → ToolCall(input=...),失败 → ToolCall(parse_error=...)
  - 通过 StreamChunk 透出工具调用(见下文 StreamChunk 扩展)

**StreamChunk 扩展:** 新增可选字段 `tool_calls: Optional[list[ToolCall]] = None`,流式末尾(收到 finish_reason 时)发一次最终 chunk 携带聚合好的 tool_calls;前面的 delta chunk 该字段为 None。

### engine/adapters/claude_adapter.py(扩展)

**职责:** 在原有 content_block_delta(text)处理基础上,新增 tool_use 块聚合。

**主要改动:**
- `_convert_messages`:把中性 Message 翻译成 Anthropic content blocks(assistant.content 为含 text 和 tool_use 块的数组,tool 角色消息翻译成 user 消息含 tool_result 块)
- `chat / chat_stream`:接受 tools 参数(Anthropic 格式),放进 payload
- `chat_stream` 新增逻辑:
  - 维护 `block_buf: dict[int, {type, id, name, partial_json_str}]` 按 content_block index 累积
  - `content_block_start{type:"tool_use", id, name}` → 初始化
  - `content_block_delta{type:"input_json_delta", partial_json}` → 拼接
  - `content_block_stop{index}` → 解析 partial_json_str,成功/失败处理同 OpenAI
  - 收尾 yield 携带 ToolCall 列表的 StreamChunk

### tui/widgets/chat_area.py(扩展)

**职责:** 在普通聊天消息之外,显示工具调用轨迹。

**对外接口新增:**
- `add_tool_call(tool_name: str, params_summary: str) -> str` —— 新增一行 `→ tool_name(summary)`,返回控件 id 用于后续 update
- `update_tool_call_result(widget_id: str, success: bool, summary: str)` —— 把行更新为 `✓ tool_name(summary): summary` 或 `✗ tool_name(summary): error`

参数 summary 由 app 层根据 tool 类型从 ToolCall.input 提取(如 ReadFile 用 path,Bash 用命令前 60 字)。

### tui/app.py(改造 _process_with_llm)

**职责:** 实现单步工具调用循环。

**改造后流程伪代码:**

```
async def _process_with_llm(content):
    messages = self.conversation_manager.get_messages()
    if first call:
        prepend system message from system_prompt.build_system_prompt(...)

    tools_payload = self.registry.to_openai_format()  # 或 anthropic,看 adapter 类型

    # 第一次调用
    pending_tool_calls = []
    chat_area.add_assistant_message_start()
    async for chunk in self.llm_client.chat_stream(messages, tools=tools_payload):
        if chunk.content: chat_area.add_stream_chunk(chunk.content)
        if chunk.tool_calls: pending_tool_calls = chunk.tool_calls
    chat_area.add_assistant_message_end()

    # 把 assistant 消息(含 tool_calls)写进对话
    self.conversation_manager.add_message(Message(role=ASSISTANT, content=text, tool_calls=pending_tool_calls))

    if not pending_tool_calls:
        return  # 纯文本回复,流程结束

    # 串行执行每个工具
    for tc in pending_tool_calls:
        widget_id = chat_area.add_tool_call(tc.name, summarize(tc.input))
        if tc.parse_error:
            result = ToolResult(content=tc.parse_error, is_error=True)
        else:
            result = await self.registry.execute(tc.name, tc.input)
        chat_area.update_tool_call_result(widget_id, not result.is_error, brief(result.content))
        self.conversation_manager.add_message(Message(role=TOOL, content=result.content, tool_call_id=tc.id, tool_result_is_error=result.is_error))

    # 第二次调用拿最终回复(本章不再循环)
    chat_area.add_assistant_message_start()
    async for chunk in self.llm_client.chat_stream(self.conversation_manager.get_messages(), tools=tools_payload):
        if chunk.content: chat_area.add_stream_chunk(chunk.content)
        # 即便第二次又出现 tool_calls,本章忽略,不触发执行(AC17)
    chat_area.add_assistant_message_end()
    # 第二次回复也写入 conversation,不带 tool_calls(本章约束)
```

**Adapter 选格式:** 在 MewCodeApp.__init__ 或 on_mount 中,根据 self.llm_client 类型(isinstance ClaudeAdapter)决定 tools_payload 用 anthropic 还是 openai。封装成一个小 helper `_build_tools_payload(client, registry)`。

### config.py / config.yaml(扩展)

config.yaml 新增:

```yaml
tools:
  enabled: "all"          # "all" | "readonly" | [ReadFile, Glob, Grep, ...]
  bash_timeout: 30
  max_output_chars: 10000
```

config.py 增加 `get_tools_config(config) -> dict`,带默认值。

## 模块交互

### 启动期(MewCodeApp.on_mount)

```
MewCodeApp.on_mount
  ├─ load_config() → config dict
  ├─ ToolContext(working_dir=os.getcwd(), os_name=..., shell=...)
  ├─ registry = build_default_registry(ctx, config)
  │       └─ 注册 6 工具 → 按 config["tools"]["enabled"] 启用
  └─ self.tool_registry = registry
     self.tool_context = ctx
```

LLM 客户端仍按现有逻辑在首次 _process_with_llm 时延迟创建。

### 单步对话流程(用户发一条需要工具的消息)

```
User input
   │
   ▼
MewCodeApp._handle_message
   │
   ▼
MewCodeApp._process_with_llm  ← 改造后入口
   │
   ├─[1]─ 注入 system prompt(首次)
   │      build_system_prompt(ctx, registry)
   │
   ├─[2]─ 准备 tools payload
   │      _build_tools_payload(client, registry)
   │      ├─ ClaudeAdapter → registry.to_anthropic_format()
   │      └─ 其他 → registry.to_openai_format()
   │
   ├─[3]─ 第一次 chat_stream(messages, tools)
   │      ├─ 边渲染 chunk.content 到 ChatArea
   │      └─ 累积 chunk.tool_calls
   │
   ├─[4]─ 写 assistant 消息(含 tool_calls)进 ConversationManager
   │
   ├─[5]─ 若无 tool_calls:结束
   │
   ├─[6]─ 对每个 ToolCall(串行,本章不并发):
   │      ├─ chat_area.add_tool_call(name, summary)  → widget_id
   │      ├─ if tc.parse_error: 直接造 isError ToolResult
   │      ├─ else:             registry.execute(name, input)  → ToolResult
   │      ├─ chat_area.update_tool_call_result(widget_id, success, brief)
   │      └─ ConversationManager.add_message(role=TOOL, content=result.content,
   │                                          tool_call_id=tc.id,
   │                                          tool_result_is_error=result.is_error)
   │
   └─[7]─ 第二次 chat_stream(messages, tools)  ← 本章到此为止
          ├─ 渲染最终回复
          └─ 第二次响应中即便又出现 tool_calls,忽略(AC17)
          → 写 assistant 消息(不带 tool_calls)进 conversation
```

### 协议翻译(发生在 Adapter 内部)

请求方向:Conversation messages → 协议 payload

```
Adapter._convert_messages(messages):
  for msg in messages:
    OpenAI 协议:
      USER     → {role:"user", content}
      ASSISTANT→ {role:"assistant", content, tool_calls?:[{id,type:"function",function:{name,arguments:json.dumps(input)}}]}
      TOOL     → {role:"tool", tool_call_id, content}
      SYSTEM   → {role:"system", content}

    Anthropic 协议(非 system 消息):
      USER     → {role:"user", content:[{type:"text", text:content}]}
                 或聚合连续 TOOL 消息为 {role:"user", content:[{type:"tool_result", tool_use_id, content, is_error?}, ...]}
      ASSISTANT→ {role:"assistant", content:[{type:"text", text}, {type:"tool_use", id, name, input}, ...]}
      SYSTEM   → 抽出来作为 top-level system 字段
```

注意点:
- Anthropic 把多个连续 TOOL 消息聚合成单条 user 消息内的多个 tool_result block(协议要求)
- OpenAI 协议 tool 消息保持独立,每条对应一个 tool_call_id
- 两种翻译都在 _convert_messages 内部完成,上层无感

响应方向:协议流式事件 → ToolCall

```
OpenAI 流式:
  delta.content                       → StreamChunk(content=...)
  delta.tool_calls[i].function.name   → buf[i].name = ...
  delta.tool_calls[i].function.arguments → buf[i].arguments_str += ...
  delta.tool_calls[i].id              → buf[i].id = ...
  finish_reason="tool_calls"          → 解析 buf,yield StreamChunk(tool_calls=[...])

Anthropic 流式:
  content_block_start{type:"text"}    → 准备 text 块
  content_block_delta{text}           → StreamChunk(content=text)
  content_block_start{type:"tool_use",id,name} → buf[i] = {id,name,partial_json:""}
  content_block_delta{partial_json}   → buf[i].partial_json += partial_json
  content_block_stop{index}           → 解析 buf[index].partial_json
  message_stop                       → yield StreamChunk(tool_calls=[...])
```

### 数据流总览

```
用户输入 ──→ MewCodeApp ──→ ConversationManager ──→ LLMClient ──→ HTTP API
                │                                       ▲
                │                                       │ tools payload
                │                                  ToolRegistry
                │                                       ▲
                │                                       │ register / list
                │                                  Tool 子类×6
                │                                       ▲
                ▼                                       │ ctx
            ChatArea  ←── ToolResult ←── execute ──── ToolContext
            (轨迹显示)
```

## 文件组织

```
project/
├── specs/
│   └── 02-tools/
│       ├── spec.md       — 已生成
│       ├── plan.md       — 本文档
│       ├── task.md       — 阶段三产出
│       └── checklist.md  — 阶段四产出
│
├── src/mewcode/
│   ├── engine/
│   │   ├── models/
│   │   │   ├── message.py   ← 扩展:ToolCall + Message 新字段 + StreamChunk 扩展
│   │   │   └── client.py    ← 扩展:chat / chat_stream 增加 tools 参数
│   │   │
│   │   ├── adapters/
│   │   │   ├── custom_adapter.py    ← 扩展:tool_calls 流式聚合 + _convert_messages 翻译
│   │   │   ├── openai_adapter.py    ← 扩展:同上
│   │   │   ├── ollama_adapter.py    ← 扩展:同上
│   │   │   └── claude_adapter.py    ← 扩展:content block 流式聚合 + _convert_messages 翻译
│   │   │
│   │   ├── tools/                   ← 全新目录
│   │   │   ├── __init__.py          — build_default_registry 工厂
│   │   │   ├── base.py              — Tool 抽象基类、ToolResult、ToolContext、ToolError
│   │   │   ├── registry.py          — ToolRegistry
│   │   │   ├── system_prompt.py     — build_system_prompt(ctx, registry)
│   │   │   ├── read_file.py         — ReadFileTool
│   │   │   ├── write_file.py        — WriteFileTool
│   │   │   ├── edit_file.py         — EditFileTool
│   │   │   ├── bash.py              — BashTool
│   │   │   ├── glob.py              — GlobTool
│   │   │   └── grep.py              — GrepTool
│   │   │
│   │   └── conversation.py          ← 不动(自动获得新 Message 字段的持久化能力)
│   │
│   ├── tui/
│   │   ├── app.py                   ← 改造:_process_with_llm 单步工具流程 + 启动期注册工具
│   │   └── widgets/
│   │       └── chat_area.py         ← 扩展:add_tool_call / update_tool_call_result
│   │
│   └── config.py                    ← 扩展:get_tools_config(config)
│
├── config.yaml                      ← 扩展:tools 节点
│
└── tests/
    ├── test_tools_base.py           — Tool / ToolResult / ToolContext 行为
    ├── test_tools_registry.py       — 注册、启用策略、调度
    ├── test_tools_read_file.py      — 6 个工具各一个文件,覆盖成功 + 所有错误分支
    ├── test_tools_write_file.py
    ├── test_tools_edit_file.py
    ├── test_tools_bash.py
    ├── test_tools_glob.py
    ├── test_tools_grep.py
    ├── test_message_tool_calls.py   — Message/ToolCall 序列化、向后兼容
    ├── test_adapter_tool_calls.py   — OpenAI 流式 tool_calls 聚合(用 mock 字节流)
    └── test_adapter_anthropic_tool_use.py  — Anthropic content block 聚合
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 工具描述形式 | 类属性 + 手写 input_schema dict | 项目现有依赖只有 textual/httpx/pyyaml/rich,引入 pydantic 不值得;手写 schema 完全可控,且工具描述是回报率最高的工程,值得手写 |
| 协议中性化点 | Message 模型(中性 OpenAI 风格) | 默认走 OpenAI 路线只需透传,Claude 路线在一处集中翻译;反过来选 Anthropic 风格会让多 3 个 Adapter 翻译。最小工作量 |
| 协议形态翻译位置 | Adapter._convert_messages | 现有架构既有约定,继续保持「上层不感知协议」(N9) |
| 流式聚合的实现位置 | 各 Adapter 的 chat_stream 内部 | 协议事件解析与 Adapter 强耦合,不应抽到外面;ToolCall 数据类则跨 Adapter 共享 |
| 工具调用透出方式 | StreamChunk 增加 tool_calls 字段 | 复用现有 chat_stream 的 yield 机制,不引入新事件类型;调用方的 async for 循环只需多检查一个字段 |
| ToolContext 在哪锁定 | MewCodeApp.on_mount 时 os.getcwd() | 与「以启动时 cwd 为根」的需求(F3 / AC4)直接对应;运行期不变,可注入到所有工具 |
| 路径解析 | ToolContext.resolve_path,绝对路径直接用,相对路径基于 working_dir | 同时满足 LLM 可能发相对/绝对路径的现实(澄清问题 6) |
| 二进制检测 | 读文件前 512 字节,含 \x00 判定 | 简单可靠,无新依赖;跨平台一致 |
| EditFile 唯一性 | str.count + str.replace 一次 | 模型把上下文 + 旧片段一起传,通常足以保证唯一;否则按错误返回让模型补足上下文 |
| Bash 输出截断 | >10000 字符时保留前 2000 + 后 8000 + 中间标记 | 与 spec N5 一致;尾部更重要(测试结果、错误堆栈通常在尾部) |
| Bash 超时 | 默认 30 秒,可 config 覆盖,超时算 isError | 防止 sleep / 死循环卡住 Agent |
| Bash shell | 跨平台:Windows 用 cmd /c,Unix 用 sh -c;用 asyncio.create_subprocess_shell | 简单一致,后续若要支持 powershell 在 ToolContext 加字段即可 |
| 噪音目录 | 硬编码 EXCLUDE_DIRS = {.git, node_modules, vendor, __pycache__, .idea, .venv, venv, build, dist} | spec 列了 5 个,顺手补上 Python 常见的 .venv/build/dist;不做配置项,后续按需扩展 |
| 工具调用串行 | 即使 ReadFile 等工具 is_concurrency_safe=True,本章串行 | 减少调度复杂度;并发执行留给 Agent Loop 章节 |
| 第二次回复中的 tool_calls | 忽略,不触发执行 | 严格满足「单步」边界(AC17);自动循环留给下一章 |
| Tool 实例的生命周期 | 启动时实例化一次,注册到 registry | 工具基本无状态,无需每次新建 |
| Adapter 选 tools 协议格式 | 在 MewCodeApp 中按 isinstance 判断 | 简单明确;Adapter 自身不承担「我用哪种格式输出」的职责,因为 to_*_format 已经在 ToolRegistry |
| Session 序列化兼容 | Message.to_dict 仅写非空新字段,from_dict 用 .get | 老 session 文件加载零变动(AC15) |
| 系统级异常处理 | ToolError 是 sentinel 类型,但本章工具实现里**不主动抛**;凡是从工具内部漏出来的非 ToolError 异常,registry.execute 用 try/except 兜底成 isError 结果 | spec F4:可恢复错误回 ToolResult,系统级才上抛 |
| system prompt 注入位置 | 每次 chat_stream 调用前重建,不持久化进 conversation | 工作目录、OS、工具列表理论上启动后不变,但每次重建可保证准确;不入 conversation 避免污染历史 |
| TUI 工具轨迹刷新 | add_tool_call 返回 widget_id,执行完用 update_tool_call_result | 简单且与现有 chat_area 风格一致(参考流式占位符) |
| 测试中如何模拟流式 | 自定义 async generator 直接 feed httpx 字节,不起 mock server | 现有 test_e2e.py 模式;轻量、不依赖网络 |
| 工具描述/system prompt 语言 | 全英文 | N11 语言策略 |
| TUI 文案 | 中文 | N11 语言策略 |
