# MewCode 工具系统(单步) Checklist

> 每一项通过运行代码或观察行为来验证,聚焦系统行为。

## 实现完整性

- [ ] tools/base.py 提供 Tool / ToolResult / ToolContext / ToolError 四个核心类型,均可被外部 import(验证:`python -c "from mewcode.engine.tools.base import Tool, ToolResult, ToolContext, ToolError; print('ok')"` 输出 ok)
- [ ] ToolContext.resolve_path 对绝对路径直接返回,对相对路径以 working_dir 为根解析(验证:test_tools_base.py 中对应测试通过)
- [ ] ToolRegistry 支持 register、enable("all"/"readonly"/list)、get、list_enabled、to_openai_format、to_anthropic_format、async execute,且执行时找不到工具/校验失败/工具异常都返回 isError 不传播(验证:test_tools_registry.py 通过)
- [ ] 6 个内置工具(ReadFile / WriteFile / EditFile / Bash / Glob / Grep)全部实现,通过 `python -c "from mewcode.engine.tools import build_default_registry; from mewcode.engine.tools.base import ToolContext; from pathlib import Path; reg = build_default_registry(ToolContext(Path.cwd(),'windows','cmd'), {}); print([t.name for t in reg.list_enabled()])"` 输出 6 个英文名
- [ ] system_prompt.build_system_prompt 输出非空字符串,内含 `Working directory:`、`Host OS:`、`Reply to the user in Chinese`(验证:`python -c` 直接调用)
- [ ] Message 模型新增 ToolCall 数据类,Message 新增 tool_calls / tool_call_id / tool_result_is_error 三个可选字段,StreamChunk 新增 tool_calls 字段(验证:test_message_tool_calls.py 通过)
- [ ] LLMClient.chat / chat_stream 抽象签名包含 tools 参数(验证:`python -c "import inspect; from mewcode.engine.models.client import LLMClient; print('tools' in inspect.signature(LLMClient.chat).parameters)"` 输出 True)
- [ ] CustomAdapter / OpenAIAdapter / OllamaAdapter / ClaudeAdapter 都接受 tools 参数,且 _convert_messages 能处理含 tool_calls 的 assistant 消息和 role:tool 消息(验证:test_adapter_tool_calls.py / test_adapter_anthropic_tool_use.py 通过)

## 工具行为正确性

- [ ] ReadFile 读已知文本文件返回带行号前缀的内容(验证:`python -c` 调用并打印,首行形如 `1\t...`)
- [ ] ReadFile 读不存在的路径返回 isError=True 且 content 含 "not found"(验证:test_tools_read_file.py)
- [ ] ReadFile 读二进制文件(造一个含 \\x00 的临时文件)返回 isError=True 且建议改用 Bash(验证:test_tools_read_file.py)
- [ ] WriteFile 写到深层不存在路径(如 a/b/c/d.txt)能成功创建父目录,文件存在且内容正确(验证:test_tools_write_file.py)
- [ ] EditFile 替换唯一片段成功并返回包含修改位置预览(验证:test_tools_edit_file.py)
- [ ] EditFile old_string 出现 0 次或多次都返回 isError 且错误信息中含次数(验证:test_tools_edit_file.py)
- [ ] Bash 执行 `echo hello` 返回 exit_code=0 且输出含 hello(验证:test_tools_bash.py)
- [ ] Bash 执行 `python -c "import sys; sys.exit(7)"` 返回 exit_code=7 且 is_error=False(验证:test_tools_bash.py)
- [ ] Bash 设 timeout=1 跑 `python -c "import time; time.sleep(3)"` 返回 is_error=True 且消息含 "timed out"(验证:test_tools_bash.py)
- [ ] Bash 输出 >10000 字符时被截断,可见首尾保留 + 中间标记(验证:test_tools_bash.py 跑 `python -c "print('x'*20000)"`)
- [ ] Glob 在项目根搜 `**/*.py` 能列出 src/mewcode 下的 .py 文件,结果按 mtime 倒序(验证:`python -c` 调用,看到 most recently modified .py 在前)
- [ ] Glob 不会把 .git / .venv / __pycache__ / node_modules 中的文件加入结果(验证:test_tools_glob.py 临时建噪音目录确认)
- [ ] Grep 输出格式为 `path:line: content`(验证:`python -c` 跑 pattern="def ",看输出每行三段冒号分隔)
- [ ] Grep 不在二进制文件上匹配、不进入噪音目录(验证:test_tools_grep.py)
- [ ] Grep 命中超过 100 时被截断,truncated 标志体现在 metadata 或 content(验证:test_tools_grep.py)

## 协议适配

- [ ] OpenAI 协议族 chat_stream 收到流式 tool_calls 增量序列(id, function.name, function.arguments 增量)能聚合成完整 ToolCall,parse_json 失败时 parse_error 字段非空,无异常抛出(验证:test_adapter_tool_calls.py 通过)
- [ ] Anthropic 协议 chat_stream 收到 content_block_start(tool_use)+ input_json_delta + content_block_stop 能聚合成完整 ToolCall(验证:test_adapter_anthropic_tool_use.py 通过)
- [ ] _convert_messages 处理含 tool_calls 的 assistant 消息时,OpenAI 协议输出 `{role:"assistant", content, tool_calls:[{id,type:"function",function:{name,arguments:json_string}}]}` 结构(验证:测试中检查 dict 字段)
- [ ] _convert_messages 处理 role=TOOL 消息时,OpenAI 协议输出 `{role:"tool", tool_call_id, content}`,Anthropic 协议把连续 TOOL 消息聚合为单条 user 消息含多个 tool_result block(验证:test_adapter_*.py 中相应断言)

## 集成

- [ ] MewCodeApp.on_mount 时创建 ToolContext(working_dir=os.getcwd(), os_name, shell)并构造 ToolRegistry,可通过 `app.tool_registry.list_enabled()` 验证(验证:启动 TUI 后日志含 "ToolRegistry" 相关或代码 import 检查通过)
- [ ] 每次 LLM 请求实际发出的 system 段中包含当前工作目录路径、操作系统标识、英文工具使用原则(验证:在 _process_with_llm 末尾加临时 logger.debug 打印 messages,运行一次后看日志内容)
- [ ] 进入 TUI 输入「读一下 config.yaml」,出现工具调用轨迹 `→ ReadFile(config.yaml)` 后变 `✓`,模型最终中文回复中包含文件中已知字段 `mimo-v2.5-pro`(验证:手动启动 `./start.ps1` 观察)
- [ ] 在 TUI 中工具调用展示与普通 user/assistant 消息样式有可见区分(`→` `✓` `✗` 前缀,样式 dim/cyan/red)(验证:同上,看截图或屏幕)
- [ ] config.yaml 中 tools.enabled 设置为 `[ReadFile, Glob, Grep]` 重启后,registry.list_enabled() 长度为 3,且模型能力告知里也只有 3 个(验证:修改 config.yaml 后跑 `python -c "from mewcode.config import load_config; from mewcode.engine.tools import build_default_registry; from mewcode.engine.tools.base import ToolContext; from pathlib import Path; reg = build_default_registry(ToolContext(Path.cwd(),'windows','cmd'), load_config()); print([t.name for t in reg.list_enabled()])"`)
- [ ] 单步流程:模型第一次回复请求工具 → 执行 → 第二次回复给最终答案。第二次回复中即便又出现 tool_calls,本章不再触发执行(验证:用 mock LLM 客户端或检查 _process_with_llm 代码逻辑,通过临时打印 pending_tool_calls 确认第二次的 tool_calls 没被处理)
- [ ] 工具执行失败(读不存在的文件)时,模型仍能拿到 isError 的工具结果并基于此给出回复(验证:在 TUI 输入「读一下 不存在的文件.txt 然后告诉我什么情况」,观察模型最终回复合理处理了错误)
- [ ] 旧版生成的 session YAML 文件(如 `~/.mewcode/sessions/` 下已有文件)能正常加载不报错(验证:启动 TUI 看日志无异常,或写一个测试 case 加载老格式 dict)

## 编译与测试

- [ ] 项目可正常启动:`./start.ps1` 进入 TUI 不报错(验证:Windows PowerShell 跑命令观察)
- [ ] `python -m pytest tests/ -v` 全部通过(已有测试 + 新增测试)(验证:跑命令看 PASSED 数量)
- [ ] 新增测试覆盖每个工具的成功路径与所有错误分支:test_tools_*.py 共 8 个文件,每个工具至少 3 个测试 case(验证:`python -m pytest tests/test_tools_*.py -v --tb=short` 通过且 case 数 >= 24)
- [ ] 新增测试覆盖流式 tool_calls 聚合(OpenAI + Anthropic):test_adapter_tool_calls.py 与 test_adapter_anthropic_tool_use.py 都通过(验证:`python -m pytest tests/test_adapter_*.py -v` PASSED)
- [ ] 新增测试覆盖 Message 序列化向后兼容:老格式 dict from_dict 不抛错且新字段为 None(验证:test_message_tool_calls.py::test_legacy_message_loads PASSED)

## 语言策略

- [ ] 抓取一次实际的 LLM 请求 payload,messages 数组中 system 字段、所有工具描述、所有给模型看的字符串均为英文(验证:在 _process_with_llm 中临时 logger.debug 打印 payload,跑一次对话后人工检查日志)
- [ ] TUI 中显示给用户的文本(状态、错误提示、欢迎信息)均为中文(英文 status_bar 文本如 "Idle/Thinking" 是上一版既有,本章不强制改)(验证:启动 TUI 触发各路径肉眼看)
- [ ] 工具实现内的所有英文字符串(name、description、错误返回的 content)无中文混入(验证:`grep -P "[\x{4e00}-\x{9fa5}]" src/mewcode/engine/tools/*.py` 应无输出)

## 端到端场景

- [ ] **场景 1:读文件并解释**——用户输入「读一下 src/mewcode/config.py 解释一下加载流程」→ TUI 出现 `→ ReadFile(...)` → `✓ ReadFile(...)` → 模型中文最终回复内容引用了 config.py 中实际存在的函数名(如 `load_config` / `get_model_config`)。整个流程一次完成,无 Python 异常(验证:手动跑 `./start.ps1` 观察)
- [ ] **场景 2:工具失败优雅处理**——用户输入「读 不存在的文件.xyz」→ TUI 出现 `→ ReadFile(...)` → `✗ ReadFile(...): File not found...` → 模型中文最终回复合理告知用户文件不存在,程序未崩溃(验证:手动跑观察)
- [ ] **场景 3:Bash 命令执行**——用户输入「运行 echo hello world」→ TUI 出现 `→ Bash(echo hello world)` → `✓ Bash(...)` → 模型最终回复中提到 `hello world`(验证:手动跑观察)
- [ ] **场景 4:配置控制**——把 config.yaml 中 tools.enabled 改为 `[Glob, Grep]`,重启,输入「请读一下 config.yaml」→ 模型应当无 ReadFile 可用,要么不调用工具直接回复说没权限,要么用 Grep 间接达成(验证:手动跑观察,确认未触发 ReadFile 调用)
- [ ] **场景 5:纯对话回归**——输入「你好,介绍下自己」→ 模型不调用任何工具,直接给文字回复;TUI 中无 `→`/`✓`/`✗` 行(验证:手动跑观察,确认上一版的纯对话行为完全保留)
