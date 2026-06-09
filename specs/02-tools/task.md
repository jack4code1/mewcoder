# MewCode 工具系统(单步) Tasks

> 共 18 个任务,按依赖顺序排列。每个任务 2-5 分钟可完成,带具体验证命令。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/mewcode/engine/tools/__init__.py` | 暴露 build_default_registry |
| 新建 | `src/mewcode/engine/tools/base.py` | Tool 抽象基类、ToolResult、ToolContext、ToolError |
| 新建 | `src/mewcode/engine/tools/registry.py` | ToolRegistry |
| 新建 | `src/mewcode/engine/tools/read_file.py` | ReadFileTool |
| 新建 | `src/mewcode/engine/tools/write_file.py` | WriteFileTool |
| 新建 | `src/mewcode/engine/tools/edit_file.py` | EditFileTool |
| 新建 | `src/mewcode/engine/tools/bash.py` | BashTool |
| 新建 | `src/mewcode/engine/tools/glob.py` | GlobTool |
| 新建 | `src/mewcode/engine/tools/grep.py` | GrepTool |
| 新建 | `src/mewcode/engine/tools/system_prompt.py` | build_system_prompt |
| 修改 | `src/mewcode/engine/models/message.py` | 增加 ToolCall + Message 新字段 + StreamChunk.tool_calls |
| 修改 | `src/mewcode/engine/models/client.py` | chat / chat_stream 增加 tools 参数 |
| 修改 | `src/mewcode/engine/adapters/custom_adapter.py` | OpenAI tool_calls 流式聚合 + 协议翻译 |
| 修改 | `src/mewcode/engine/adapters/openai_adapter.py` | 同上 |
| 修改 | `src/mewcode/engine/adapters/ollama_adapter.py` | 同上 |
| 修改 | `src/mewcode/engine/adapters/claude_adapter.py` | Anthropic content block 聚合 + 协议翻译 |
| 修改 | `src/mewcode/tui/widgets/chat_area.py` | add_tool_call / update_tool_call_result |
| 修改 | `src/mewcode/tui/app.py` | 启动期注册工具 + 单步工具调用流程 |
| 修改 | `src/mewcode/config.py` | get_tools_config |
| 修改 | `config.yaml` | tools 节点 |
| 新建 | `tests/test_tools_base.py` | Tool/ToolResult/ToolContext 行为 |
| 新建 | `tests/test_tools_registry.py` | 注册、启用策略、调度 |
| 新建 | `tests/test_tools_read_file.py` | ReadFile 全分支 |
| 新建 | `tests/test_tools_write_file.py` | WriteFile 全分支 |
| 新建 | `tests/test_tools_edit_file.py` | EditFile 全分支 |
| 新建 | `tests/test_tools_bash.py` | Bash 全分支(超时、截断、非零退出) |
| 新建 | `tests/test_tools_glob.py` | Glob 全分支 |
| 新建 | `tests/test_tools_grep.py` | Grep 全分支 |
| 新建 | `tests/test_message_tool_calls.py` | Message/ToolCall 序列化 + 向后兼容 |
| 新建 | `tests/test_adapter_tool_calls.py` | OpenAI 流式 tool_calls 聚合 |
| 新建 | `tests/test_adapter_anthropic_tool_use.py` | Anthropic content block 聚合 |

---

## T1: 建立 engine/tools 目录与基础类型

**文件:** `src/mewcode/engine/tools/__init__.py`、`src/mewcode/engine/tools/base.py`
**依赖:** 无

**步骤:**
1. 新建 `src/mewcode/engine/tools/` 目录,放空的 `__init__.py`(后续 T10 再补 build_default_registry)
2. 新建 `base.py`,定义:
   - `class ToolError(Exception)`:系统级错误标记类
   - `@dataclass class ToolResult`:字段 `content: str`、`is_error: bool = False`、`metadata: dict = field(default_factory=dict)`
   - `@dataclass class ToolContext`:字段 `working_dir: Path`、`os_name: str`、`platform_shell: str`;实例方法 `resolve_path(p: str) -> Path`(绝对路径直接 `Path(p)`,否则 `self.working_dir / p`,然后 `.resolve()`)
   - `class Tool(ABC)`:类属性 `name: str = ""`、`description: str = ""`、`input_schema: dict = {}`、`category: str = ""`、`is_read_only: bool = False`、`is_destructive: bool = False`、`is_concurrency_safe: bool = False`;方法 `validate_input(input: dict) -> Optional[str]`(默认返回 None);抽象方法 `async execute(ctx: ToolContext, input: dict) -> ToolResult`

**验证:** `python -c "from mewcode.engine.tools.base import Tool, ToolResult, ToolContext, ToolError; print('ok')"` 输出 ok

---

## T2: 实现 ToolRegistry

**文件:** `src/mewcode/engine/tools/registry.py`
**依赖:** T1

**步骤:**
1. `class ToolRegistry`,构造函数接受 `ctx: ToolContext`,内部 `self._tools: dict[str, Tool] = {}`、`self._enabled: set[str] = set()`
2. `register(tool: Tool)`:重名抛 ValueError,默认加入 _enabled
3. `enable(spec)`:接受 `"all"` / `"readonly"` / `list[str]`;`"readonly"` 只启用 `is_read_only=True` 的工具;列表则按名启用,未知名忽略并 logger.warning
4. `get(name) -> Optional[Tool]`、`list_enabled() -> list[Tool]`
5. `to_openai_format() -> list[dict]`:`[{type:"function", function:{name, description, parameters: input_schema}}]`,只输出已启用
6. `to_anthropic_format() -> list[dict]`:`[{name, description, input_schema}]`,只输出已启用
7. `async execute(name, input) -> ToolResult`:
   - 工具找不到 → ToolResult(content=f"Tool '{name}' is not registered or disabled.", is_error=True)
   - validate_input 返回错误字符串 → ToolResult(content=err, is_error=True)
   - try await tool.execute(ctx, input);except ToolError 重新抛;except Exception as e → ToolResult(content=f"Tool execution failed: {e}", is_error=True)
   - 在 try/except 外用 logger.info 记录工具名/耗时/是否错误

**验证:** 写一个简单内存 Tool 子类(execute 返回固定 ToolResult)注册并 `await reg.execute("name", {})`,断言行为。可临时写到 `python -c` 命令中跑通

---

## T3: 实现 ReadFileTool

**文件:** `src/mewcode/engine/tools/read_file.py`
**依赖:** T1

**步骤:**
1. `class ReadFileTool(Tool)`,name="ReadFile",is_read_only=True,is_concurrency_safe=True,category="file"
2. description(英文,4-8 行):"Read the contents of a file. Use it after locating the file with Grep/Glob. Path can be absolute or relative to the working directory. Returns content with line-number prefixes (e.g. `1\\tdef main():`). Use offset/limit for large files. Refuses binary files."
3. input_schema:`{type:"object", properties:{path:{type:"string"}, offset:{type:"integer", minimum:0}, limit:{type:"integer", minimum:1}}, required:["path"]}`
4. validate_input:path 为空字符串返回错误
5. execute:
   - 用 ctx.resolve_path 解析路径
   - 文件不存在 → isError "File not found: <path>"
   - 不是文件 → isError "Not a regular file: <path>"
   - 读前 512 字节,含 b"\\x00" → isError "Binary file detected. Use Bash with appropriate tools to inspect."
   - 用 utf-8 errors=replace 读全文,按 \\n 切行
   - offset/limit 应用:lines = lines[offset:offset+limit]
   - 拼接 `f"{i+1}\\t{line}"`,以 \\n 连接
   - 成功:ToolResult(content=text, metadata={"path": str(p), "lines": len(lines)})

**验证:** 在 tests/ 写 case(T11 任务里),手动验证可临时 `python -c "import asyncio; from mewcode.engine.tools.read_file import ReadFileTool; from mewcode.engine.tools.base import ToolContext; from pathlib import Path; ctx=ToolContext(Path.cwd(), 'windows', 'cmd'); print(asyncio.run(ReadFileTool().execute(ctx, {'path':'config.yaml'})).content[:80])"`

---

## T4: 实现 WriteFileTool

**文件:** `src/mewcode/engine/tools/write_file.py`
**依赖:** T1

**步骤:**
1. `class WriteFileTool(Tool)`,name="WriteFile",is_read_only=False,category="file"
2. description:"Write content to a file, creating parent directories if needed. Overwrites existing files. Path can be absolute or relative to the working directory."
3. input_schema:`{type:"object", properties:{path:{type:"string"}, content:{type:"string"}}, required:["path","content"]}`
4. execute:
   - 解析路径
   - p.parent.mkdir(parents=True, exist_ok=True)
   - p.write_text(content, encoding="utf-8")
   - ToolResult(content=f"Wrote {len(content)} bytes to {p}", metadata={"path": str(p), "bytes": len(content)})
   - 异常包成 isError

**验证:** `python -c` 调用写入到临时路径,os.path.exists 检查

---

## T5: 实现 EditFileTool

**文件:** `src/mewcode/engine/tools/edit_file.py`
**依赖:** T1

**步骤:**
1. name="EditFile",description 强调「old_string must be unique within the file」「include enough surrounding context」「empty new_string deletes the matched text」
2. input_schema:`{type:"object", properties:{path, old_string, new_string}, required:["path","old_string","new_string"]}`
3. execute:
   - 读全文(text mode)
   - count = content.count(old_string)
   - count == 0 → isError "old_string not found in file. Your snapshot of the file may be stale; re-read the file before editing."
   - count > 1 → isError f"old_string appears {count} times in the file. Provide more surrounding context to make it unique."
   - new = content.replace(old_string, new_string, 1)
   - 写回
   - 找到修改位置:`idx = content.index(old_string)`,从 idx 起算行号;返回修改位置 ±5 行的预览(用新内容计算)
   - ToolResult(content=f"Edited {p}\\n\\nPreview (around the change):\\n{preview}", metadata={"path": str(p)})

**验证:** `python -c` 准备一个临时文件,做替换后读回断言

---

## T6: 实现 BashTool

**文件:** `src/mewcode/engine/tools/bash.py`
**依赖:** T1

**步骤:**
1. name="Bash",is_destructive=True,category="shell"
2. description:"Execute a shell command in the working directory. Stdout and stderr are merged. Default timeout is 30 seconds. Output exceeding 10000 chars is truncated (head 2000 + tail 8000). Non-zero exit codes are returned as normal results (use them to diagnose). Only timeouts are reported as errors."
3. input_schema:`{type:"object", properties:{command:{type:"string"}, timeout:{type:"integer", minimum:1, maximum:600}}, required:["command"]}`
4. execute:
   - timeout = input.get("timeout", 30)
   - 拼 shell 命令:Windows 用 `["cmd", "/c", command]`(via asyncio.create_subprocess_exec)或者 直接用 `asyncio.create_subprocess_shell(command, cwd=ctx.working_dir, stdout=PIPE, stderr=STDOUT)` 并依赖系统默认 shell;统一用 `create_subprocess_shell`,跨平台
   - try: stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
   - except TimeoutError: 杀进程 → isError f"Command timed out after {timeout}s"
   - 解码 utf-8 errors=replace
   - 截断函数:if len > 10000: head = text[:2000]; tail = text[-8000:]; truncated = head + f"\\n\\n... [{len(text)-10000} chars truncated] ...\\n\\n" + tail
   - 包内容:`<bash_output exit_code={code}>\\n{text}\\n</bash_output>`
   - ToolResult(content=..., is_error=False, metadata={"exit_code":code, "command":command, ...})

**验证:** `python -c` 执行 `echo hello` 看输出包含 `exit_code=0` 和 `hello`

---

## T7: 实现 GlobTool

**文件:** `src/mewcode/engine/tools/glob.py`
**依赖:** T1

**步骤:**
1. name="Glob",is_read_only=True,is_concurrency_safe=True,category="search"
2. description:"Find files by glob pattern (supports `**` recursive). Excludes noisy directories (.git, node_modules, .venv, etc.). Returns paths sorted by mtime descending. Capped at 200 results."
3. input_schema:`{path:{type:"string"}, pattern:{type:"string"}}`,required `pattern`,path 可选(默认 working_dir)
4. EXCLUDE_DIRS = {".git","node_modules","vendor","__pycache__",".idea",".venv","venv","build","dist"}
5. execute:
   - root = ctx.resolve_path(input.get("path") or ".")
   - 用 root.rglob(pattern) 或 root.glob(pattern);手动过滤路径,任何一段在 EXCLUDE_DIRS 里则跳过
   - 收集成 list,按 stat().st_mtime desc 排序
   - 截断到 200,记录 truncated
   - 输出:每行一个相对路径(相对于 root)
   - ToolResult(content="\\n".join(lines), metadata={"count":len, "truncated":truncated})

**验证:** 在项目根 `python -c` 跑 pattern="**/*.py" 看到 src 下的 .py,且不含 `.venv` 路径

---

## T8: 实现 GrepTool

**文件:** `src/mewcode/engine/tools/grep.py`
**依赖:** T1

**步骤:**
1. name="Grep",is_read_only=True,is_concurrency_safe=True,category="search"
2. description:"Search file contents by regex. Optionally filter files by glob, add context lines (-A/-B). Skips binary files and noisy directories. Returns `path:line: content`. Capped at 100 matches."
3. input_schema:`{pattern:{type:"string"}, path?, include?:string(glob), context?:integer(0-10)}`,required `pattern`
4. 同样的 EXCLUDE_DIRS 过滤逻辑
5. execute:
   - 编译 regex,正则错误 → isError "Invalid regex: ..."
   - 遍历 root 下所有文件,每个文件 read_bytes 读前 512 字节判二进制,跳过
   - 文本读全文,逐行 re.search;命中则记录 `path:line_no: line`(还有 -A/-B 上下文,用环形缓冲实现简单版本:维护前 N 行,命中后再读 N 行作为后文)
   - 总计达到 100 立即停止,记录 truncated
   - ToolResult(content=...,metadata)

**验证:** `python -c` 搜 "def " 或者搜某个已知字符串,看输出格式正确

---

## T9: 实现 build_system_prompt

**文件:** `src/mewcode/engine/tools/system_prompt.py`
**依赖:** T2

**步骤:**
1. `def build_system_prompt(ctx: ToolContext, registry: ToolRegistry) -> str`
2. 返回英文字符串,模板:

```
You are MewCode, an autonomous coding assistant.

Working directory: <working_dir>
Host OS: <os_name>

You have access to file/shell/search tools. Guidelines:
- Use Grep/Glob to locate code before reading.
- For EditFile, include enough surrounding context in old_string to make the match unique within the file.
- Bash output is merged (stdout+stderr) and truncated if too long; do not rely on full output for very chatty commands.
- Paths can be absolute or relative to the working directory.

Reply to the user in Chinese, but think and call tools in English.
```

**验证:** `python -c "from mewcode.engine.tools.system_prompt import build_system_prompt; from mewcode.engine.tools.base import ToolContext; from mewcode.engine.tools.registry import ToolRegistry; from pathlib import Path; ctx=ToolContext(Path.cwd(),'windows','cmd'); reg=ToolRegistry(ctx); print(build_system_prompt(ctx, reg))"` 输出包含 `Working directory:`、`Host OS:`、`Reply to the user in Chinese`

---

## T10: 完善 tools/__init__.py(build_default_registry)

**文件:** `src/mewcode/engine/tools/__init__.py`
**依赖:** T1, T2, T3, T4, T5, T6, T7, T8

**步骤:**
1. 导入 6 个工具类和 ToolRegistry
2. `def build_default_registry(ctx: ToolContext, config: dict) -> ToolRegistry`:
   - reg = ToolRegistry(ctx)
   - 实例化 6 个工具,reg.register(...)
   - tools_cfg = config.get("tools", {})
   - enabled = tools_cfg.get("enabled", "all")
   - reg.enable(enabled)
   - return reg

**验证:** `python -c` 跑一遍,断言 reg.list_enabled() 长度为 6

---

## T11: 写工具单测

**文件:** `tests/test_tools_base.py`、`tests/test_tools_registry.py`、`tests/test_tools_read_file.py`、`tests/test_tools_write_file.py`、`tests/test_tools_edit_file.py`、`tests/test_tools_bash.py`、`tests/test_tools_glob.py`、`tests/test_tools_grep.py`
**依赖:** T2, T3, T4, T5, T6, T7, T8, T10

**步骤(每个文件按下面要点写,每文件 3-8 个测试):**

1. **test_tools_base.py**:ToolContext.resolve_path(绝对/相对/不存在)、ToolResult dataclass 默认值、Tool 子类化基础
2. **test_tools_registry.py**:register 重名抛错;enable("all")/enable("readonly")/enable(列表)/enable(未知名忽略);to_openai_format/to_anthropic_format 字段正确;execute 找不到工具/校验失败/工具抛异常都返回 isError 不传播
3. **test_tools_read_file.py**:成功读 + 行号格式;offset/limit;不存在;二进制(造一个 \\x00 文件);路径为空 validate_input 错误
4. **test_tools_write_file.py**:写新文件;父目录递归创建;覆盖已存在
5. **test_tools_edit_file.py**:唯一替换 + 预览;0 次匹配;多次匹配;空 new_string 删除片段
6. **test_tools_bash.py**:`echo hello` 成功;`exit 1` 非零退出但 is_error=False;超时(`python -c "import time; time.sleep(2)"` 配合 timeout=1 → is_error=True);超长输出截断(用 `python -c "print('x'*20000)"`)
7. **test_tools_glob.py**:基础匹配;`**` 递归;EXCLUDE_DIRS 过滤(临时建 .git/foo.py 看不会出现);200 截断
8. **test_tools_grep.py**:基础匹配;regex;include glob 过滤;-C 上下文;100 截断;无效正则

用 pytest tmp_path fixture 隔离磁盘;Bash 测试用 subprocess 真实跑(跨平台:用 `python -c`)

**验证:** `python -m pytest tests/test_tools_*.py -v` 全部通过

---

## T12: 扩展 Message 模型

**文件:** `src/mewcode/engine/models/message.py`
**依赖:** 无

**步骤:**
1. 新增 `@dataclass class ToolCall`:`id: str`、`name: str`、`input: dict = field(default_factory=dict)`、`parse_error: Optional[str] = None`;实现 `to_dict` / 类方法 `from_dict`
2. Message 增加可选字段:`tool_calls: Optional[list[ToolCall]] = None`、`tool_call_id: Optional[str] = None`、`tool_result_is_error: Optional[bool] = None`(注意必须放在 metadata 后,且都有默认值)
3. Message.to_dict 仅当字段非空时输出
4. Message.from_dict 用 .get 处理新字段;tool_calls 反序列化时遍历 list 转 ToolCall
5. StreamChunk 增加 `tool_calls: Optional[list[ToolCall]] = None`

**验证:** `python -c` 构造一个 Message(role=ASSISTANT, content="hi", tool_calls=[ToolCall("c1","ReadFile",{"path":"a"})]),to_dict 后 from_dict,断言往返一致;再构造老格式 dict(只有 role+content+timestamp)from_dict,断言不抛错且新字段为 None

---

## T13: 测试 Message/ToolCall 序列化

**文件:** `tests/test_message_tool_calls.py`
**依赖:** T12

**步骤:**
1. test_tool_call_roundtrip:ToolCall.to_dict → from_dict 等价
2. test_message_with_tool_calls_roundtrip:Message(role=ASSISTANT,...,tool_calls=[...]) 往返
3. test_message_tool_role:Message(role=TOOL, content="result", tool_call_id="c1", tool_result_is_error=True) 往返
4. test_legacy_message_loads:dict={"role":"user","content":"hi","timestamp":"..."} from_dict 不抛错,新字段为 None
5. test_to_dict_omits_empty:tool_calls 为 None 时不在 to_dict 输出

**验证:** `python -m pytest tests/test_message_tool_calls.py -v` 通过

---

## T14: 扩展 LLMClient 抽象基类

**文件:** `src/mewcode/engine/models/client.py`
**依赖:** 无(可与 T12 并行)

**步骤:**
1. `chat(messages, tools: Optional[list[dict]] = None, **kwargs)` —— 抽象方法签名
2. `chat_stream(messages, tools: Optional[list[dict]] = None, **kwargs)` —— 抽象方法签名
3. docstring 说明 tools 是已经按目标协议格式化的列表

**验证:** `python -c "from mewcode.engine.models.client import LLMClient; print(LLMClient.chat.__doc__)"` 不报错;`python -m pytest tests/ -v` 现有测试不破

---

## T15: 改造 OpenAI 协议族 Adapter

**文件:** `src/mewcode/engine/adapters/custom_adapter.py`、`src/mewcode/engine/adapters/openai_adapter.py`、`src/mewcode/engine/adapters/ollama_adapter.py`
**依赖:** T12, T14

**步骤(每个 Adapter 一致改动):**
1. `_convert_messages` 改写:
   - SYSTEM/USER:不变
   - ASSISTANT:基础 dict `{role:"assistant", content: msg.content}`,如有 tool_calls 则增加 `tool_calls: [{id, type:"function", function:{name, arguments: json.dumps(input)}}]`
   - TOOL:`{role:"tool", tool_call_id: msg.tool_call_id, content: msg.content}`
2. `chat / chat_stream` 接受 tools 参数,如不为 None 则放进 payload
3. `chat_stream` 流式增量解析:
   - 维护 `tool_buf: dict[int, dict]`(index 索引)
   - 每次 delta:
     - 有 content → yield StreamChunk(content=...)
     - 有 tool_calls(数组,每项含 index 和子字段):按 index 合并 id、function.name、function.arguments(增量字符串)
   - 收到 finish_reason 且 tool_buf 非空时,逐项尝试 json.loads(args_str):
     - 成功 → ToolCall(id=buf.id, name=buf.name, input=parsed)
     - 失败 → ToolCall(id=buf.id, name=buf.name, input={}, parse_error=f"Failed to parse tool arguments: {err}")
   - yield 一个 StreamChunk(content="", finish_reason=..., tool_calls=collected)

**验证:** `python -m pytest tests/ -v` 现有测试不破;手动 `python -c` 跑 CustomAdapter._convert_messages 处理含 tool_calls 的 Message,看输出 dict 字段正确

---

## T16: 改造 Claude Adapter

**文件:** `src/mewcode/engine/adapters/claude_adapter.py`
**依赖:** T12, T14

**步骤:**
1. `_convert_messages` 改写为返回 `(system_prompt: Optional[str], messages: list[dict])`,逻辑:
   - SYSTEM 抽出
   - USER:如内容是简单文本 → `{role:"user", content:[{type:"text", text:msg.content}]}`
   - ASSISTANT:`content` 数组 = [{type:"text", text:msg.content}] + (如有 tool_calls)[{type:"tool_use", id, name, input} for tc in tool_calls]
   - TOOL 消息:**聚合连续 TOOL 消息为单条 user 消息**——遍历时收集连续 TOOL,然后拼成 `{role:"user", content:[{type:"tool_result", tool_use_id, content, is_error?} ...]}`
2. `chat / chat_stream` 接受 tools 参数,放进 payload(Anthropic 格式 `[{name, description, input_schema}]`)
3. `chat_stream` 流式增量:
   - 维护 `block_buf: dict[int, dict]`
   - `content_block_start{index, type, id?, name?}` → 初始化
   - `content_block_delta{index, delta}`:
     - delta.type == "text_delta" → yield StreamChunk(content=delta.text)
     - delta.type == "input_json_delta" → buf[index].partial_json += delta.partial_json
   - `content_block_stop{index}`:若该块 type=="tool_use",尝试 json.loads(partial_json),成功/失败造对应 ToolCall
   - `message_stop`:若收集到 tool_calls,yield 最终 StreamChunk(tool_calls=collected, finish_reason="tool_use")

**验证:** `python -m pytest tests/ -v` 现有测试不破

---

## T17: 测试流式 tool_calls 聚合

**文件:** `tests/test_adapter_tool_calls.py`、`tests/test_adapter_anthropic_tool_use.py`
**依赖:** T15, T16

**步骤:**
1. **test_adapter_tool_calls.py**(OpenAI 协议族):
   - 用 monkeypatch 替换 self.client.stream 为 async generator,直接 yield 预定义的 SSE 字节序列
   - 序列模拟 tool_calls delta:首次给 `id+function.name`,后续给 `function.arguments` 字符串增量,最后 `finish_reason="tool_calls"`
   - 断言收到的最终 StreamChunk.tool_calls 非空,id/name/input 字段正确
   - 断言 partial_json 拼接失败时 parse_error 字段非空,且不抛异常
2. **test_adapter_anthropic_tool_use.py**:
   - 模拟 Anthropic SSE 序列:message_start → content_block_start(text) → content_block_delta(text_delta) → content_block_stop → content_block_start(tool_use) → 多个 input_json_delta → content_block_stop → message_stop
   - 断言流式 yield 出文本 chunk + 最终 tool_calls chunk

3. 用 httpx.AsyncClient 的 mock_transport 或者直接 patch _stream 都可。最简单做法:把 Adapter 子类化,override `client.stream` 上下文管理器返回的对象

**验证:** `python -m pytest tests/test_adapter_tool_calls.py tests/test_adapter_anthropic_tool_use.py -v` 通过

---

## T18: TUI 工具调用轨迹与单步流程

**文件:** `src/mewcode/tui/widgets/chat_area.py`、`src/mewcode/tui/app.py`、`src/mewcode/config.py`、`config.yaml`
**依赖:** T10, T15, T16

**步骤:**

**chat_area.py:**
1. `add_tool_call(tool_name: str, params_summary: str) -> str`:生成 widget_id(如 `tool-{uuid4()}`),mount 一个 Static(`→ tool_name(params_summary)`,样式 dim/cyan),classes="chat-msg tool-msg",返回 widget_id
2. `update_tool_call_result(widget_id: str, success: bool, summary: str)`:try query_one f"#{widget_id}",update 为 `✓ tool_name(...): summary`(成功) 或 `✗ tool_name(...): summary`(失败,红色)。注意要保留原 tool_name+params,可在 add 时把它存到 widget 的属性里

**config.py:**
1. 新增 `def get_tools_config(config: dict) -> dict`:返回 `{"enabled": "all", "bash_timeout": 30, "max_output_chars": 10000}` 与 config.get("tools",{}) 合并

**config.yaml:**
1. 末尾追加:

```yaml
tools:
  enabled: "all"
  bash_timeout: 30
  max_output_chars: 10000
```

**app.py:**
1. `on_mount` 中:
   - 解析 ToolContext(working_dir=Path(os.getcwd()), os_name=platform.system().lower(), platform_shell="cmd" if windows else "sh")
   - self.tool_context = ctx
   - self.tool_registry = build_default_registry(ctx, self.config)
2. helper `_build_tools_payload(client) -> list[dict]`:isinstance(client, ClaudeAdapter) → to_anthropic_format() 否则 to_openai_format()
3. `_process_with_llm` 改造:
   - 取 messages
   - if first call(可用 self.first_call 标记或检查 messages 是否有 SYSTEM):在 messages 头插入 Message(role=SYSTEM, content=build_system_prompt(ctx, registry))(只插入到当前调用,不存进 conversation)
   - tools_payload = self._build_tools_payload(client)
   - 第一次 chat_stream:边渲染 content,边收集 chunk.tool_calls(若多次出现,以最后非空那次为准)
   - 把 assistant 消息(含 tool_calls)写进 conversation
   - 若无 tool_calls:end,return
   - 串行执行每个 tc:add_tool_call → registry.execute / 用 parse_error 造 isError → update_tool_call_result → conversation.add_message(role=TOOL, content=result.content, tool_call_id=tc.id, tool_result_is_error=result.is_error)
   - 第二次 chat_stream(tools 同样传入,但不再处理工具调用):add_assistant_message_start → 边渲染 content → end;**忽略**第二次的 tool_calls(本章约束)
4. 第二次 chat_stream 的消息要包含完整对话(含工具结果);system prompt 同样作为头部插入(每次新的 chat_stream 都重建)

**验证:**
1. 项目编译/导入:`python -c "from mewcode.tui.app import run_app; print('ok')"` 输出 ok
2. `python -m pytest tests/ -v` 全通过(包括所有新测试)
3. 启动 TUI:`./start.ps1`,输入「读一下 config.yaml 然后告诉我里面默认模型是什么」,观察:
   - 出现 `→ ReadFile(config.yaml)` 行
   - 紧接着变成 `✓ ReadFile(config.yaml): ...`
   - 模型给出中文最终回复包含 "mimo-v2.5-pro"

---

## 执行顺序

```
T1 ─┬─ T2 ─┬─ T9 ──────────┐
    │      │               │
    ├─ T3 ─┤               │
    ├─ T4 ─┤               │
    ├─ T5 ─┼─ T10 ─┬─ T11 ─┤
    ├─ T6 ─┤      │       │
    ├─ T7 ─┤      │       │
    └─ T8 ─┘      │       │
                   │       │
T12 ─────┬─ T13 ───┘       │
         │                 │
T14 ─────┤                 │
         │                 │
         ├─ T15 ─┬─ T17 ───┤
         │      │          │
         └─ T16 ┘          │
                           │
                           └─ T18(终）
```

可以并行的:
- T3-T8 六个工具实现彼此独立,完全可并行
- T12 / T14 互不依赖
- T15 / T16 都依赖 T12+T14,可并行
- T11 / T13 / T17 测试可与对应实现完成后并行
