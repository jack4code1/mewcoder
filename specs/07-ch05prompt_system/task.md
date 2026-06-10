# Chapter 05 Prompt System Tasks

## Task 1: 建立 Prompt 模块目录

### 目标

新增 `src/mewcode/engine/prompt/`，承载 Prompt 组装相关代码，避免继续把 prompt 逻辑放在 `engine/tools/system_prompt.py`。

### 文件影响

新增：

- `src/mewcode/engine/prompt/__init__.py`
- `src/mewcode/engine/prompt/sections.py`
- `src/mewcode/engine/prompt/assembler.py`
- `src/mewcode/engine/prompt/cache_control.py`
- `src/mewcode/engine/prompt/system_reminder.py`
- `src/mewcode/engine/prompt/plan_mode.py`

### 步骤

1. 创建 prompt 包。
2. 在 `__init__.py` 中导出核心类型。
3. 保持新模块不依赖 TUI 层。

### 验证

- `python -m pytest tests/ -v` 不出现 import 错误。
- 新模块可以被 `src/mewcode/engine/tools/system_prompt.py` 和 `src/mewcode/tui/app.py` 引用。

---

## Task 2: 实现七模块 Section 体系

### 目标

把扁平 System Prompt 拆成可排序、可测试的七个 Section。

### 文件影响

新增/修改：

- `src/mewcode/engine/prompt/sections.py`
- `src/mewcode/engine/tools/system_prompt.py`

### 步骤

1. 定义 `Section` dataclass：
   - `name`
   - `priority`
   - `content`
   - `render()`

2. 定义七个 Section：
   - `IdentitySection`
   - `BehaviorSection`
   - `ToolUsageSection`
   - `CodeQualitySection`
   - `SecuritySection`
   - `TaskPatternSection`
   - `OutputStyleSection`

3. 定义 `default_sections()`，返回七个默认 Section。

4. 定义 `render_system_prompt(sections)`：
   - 按 `priority` 升序排序。
   - 拼接所有 Section。
   - 返回稳定字符串。

5. 重构 `build_system_prompt()`：
   - 不再写入 working_dir / os_name / 工具列表。
   - 只返回静态七模块 System Prompt。
   - 保留兼容入口，避免调用方一次性大改。

### 验证

新增测试：

- `tests/test_prompt_sections.py`

覆盖：

- 七个 Section 都存在。
- priority 顺序稳定。
- system prompt 不包含 working directory、host OS、当前时间等动态信息。
- 多次调用输出一致。

---

## Task 3: 实现环境上下文消息

### 目标

把工作目录、OS、当前时间、Git 状态从 system 通道移到 messages 通道首条 user 消息。

### 文件影响

新增/修改：

- `src/mewcode/engine/prompt/assembler.py`
- `src/mewcode/tui/app.py`

### 步骤

1. 定义 `EnvContext` dataclass：
   - `working_dir`
   - `os_name`
   - `current_time`
   - `git_status`

2. 定义 `build_environment_message(env_context)`：
   - 返回 `Message(role=MessageRole.USER, content=...)`
   - content 使用 `<environment-context>...</environment-context>` 包裹。

3. 在 TUI 层构造 `EnvContext`：
   - `working_dir` 来自 `ToolContext`
   - `os_name` 来自 `ToolContext`
   - `current_time` 使用当前时间
   - `git_status` 允许先用轻量字符串或 unavailable

4. 确保环境消息不持久化到 conversation history，只在请求组装时临时加入。

### 验证

新增测试：

- `tests/test_prompt_assembler.py`

覆盖：

- messages[0] 是 environment-context。
- system_text 不包含环境上下文。
- 对话历史不被污染。

---

## Task 4: 实现 system-reminder 机制

### 目标

提供 role=user + XML 标签包裹的动态指令注入机制。

### 文件影响

新增：

- `src/mewcode/engine/prompt/system_reminder.py`

修改：

- `src/mewcode/engine/prompt/assembler.py`

### 步骤

1. 定义 `SystemReminder` dataclass：
   - `content`
   - `scope`
   - `source`
   - `priority`

2. 定义 scope 枚举或常量：
   - `session`
   - `turn`

3. 定义 source 枚举或常量：
   - `plan_mode`
   - `mcp`
   - `skill`
   - `memory`
   - `project_doc`
   - `custom`

4. 实现 `wrap_system_reminder()`：
   - 输出 `<system-reminder>...</system-reminder>`

5. 实现 reminder 排序：
   - 同 scope 内按 `priority` 升序。

6. 在 assembler 中支持：
   - session reminder 插入到 environment-context 之后。
   - turn reminder 插入到当前用户输入之前。

### 验证

新增测试：

- `tests/test_system_reminder.py`

覆盖：

- XML 包裹格式正确。
- session / turn reminder 注入位置正确。
- reminder 不进入 system_text。
- 对话历史顺序不被打乱。

---

## Task 5: 实现 assembleAPIPayload

### 目标

建立七源到三通道的统一组装函数。

### 文件影响

新增/修改：

- `src/mewcode/engine/prompt/assembler.py`
- `src/mewcode/tui/app.py`

### 步骤

1. 定义 `AssembledPayload` dataclass：
   - `system_text`
   - `messages`
   - `tools`
   - `cache_config`

2. 实现 `assembleAPIPayload()`：
   - 输入 sections、registry、conversation_messages、env_context、reminders、cache_config。
   - 输出 system/messages/tools 三通道。

3. 分发规则：
   - 静态 System Prompt → `system_text`
   - 环境上下文 → `messages`
   - 工具描述 → `tools`
   - 项目指令文件 → 预留 reminder source，不加载
   - 自动记忆 → 预留 reminder source，不提取
   - System Reminder → `messages`
   - 对话历史 → `messages`

4. 在 `app.py` 中替换 `_messages_with_system()`：
   - 使用 assembler 返回的 system_text + messages。
   - 兼容现有 LLMClient 接口：仍转成 `[MessageRole.SYSTEM] + messages` 传入 `chat_stream()`。

5. 保持 conversation manager 只保存真实 user / assistant / tool 消息。

### 验证

新增测试：

- `tests/test_prompt_assembler.py`
- `tests/test_prompt_integration.py`

覆盖：

- system/messages/tools 三通道输出正确。
- system_text 稳定。
- messages 注入顺序正确。
- tools payload 来源仍是 registry。
- conversation history 不持久化 environment/reminder 临时消息。

---

## Task 6: 强化 6 个工具 description

### 目标

补齐工具使用场景、优先级、配合关系，使模型更稳定地选择工具。

### 文件影响

修改：

- `src/mewcode/engine/tools/read_file.py`
- `src/mewcode/engine/tools/edit_file.py`
- `src/mewcode/engine/tools/write_file.py`
- `src/mewcode/engine/tools/bash.py`
- `src/mewcode/engine/tools/glob.py`
- `src/mewcode/engine/tools/grep.py`

### 步骤

1. ReadFile：强调先 Glob/Grep 定位，再 ReadFile；强调编辑前必须读取。
2. EditFile：强调编辑前必须 ReadFile；强调小范围修改优先 EditFile。
3. WriteFile：强调新文件或大面积重写使用；强调不要用它做小范围改动。
4. Bash：强调专用工具优先；强调测试、构建、git、系统检查适合 Bash。
5. Glob：强调按文件名/路径找文件；强调找到后配合 ReadFile 或 Grep。
6. Grep：强调按内容搜索；强调找到结果后用 ReadFile 读取完整上下文。

### 验证

新增/更新测试：

- `tests/test_tools.py` 或现有工具测试文件

覆盖：

- 六个工具 description 非空。
- description 包含关键指引词：
  - WHEN TO USE
  - WHEN NOT TO USE
  - ReadFile
  - Glob
  - Grep
  - EditFile
  - WriteFile
  - Bash

---

## Task 7: 实现 Prompt Cache 抽象与 usage 扩展

### 目标

让缓存控制成为统一模型，同时对不支持 provider 做兼容降级。

### 文件影响

新增：

- `src/mewcode/engine/prompt/cache_control.py`

修改：

- `src/mewcode/engine/models/message.py`
- `src/mewcode/engine/adapters/_openai_protocol.py`
- `src/mewcode/engine/adapters/claude_adapter.py`
- `src/mewcode/engine/adapters/openai_adapter.py`
- `src/mewcode/engine/adapters/custom_adapter.py`
- `src/mewcode/engine/adapters/ollama_adapter.py`

### 步骤

1. 定义 `CacheConfig`。
2. 定义 `CacheUsage`。
3. 扩展 `TokenUsage`：
   - `cache_creation_input_tokens`
   - `cache_read_input_tokens`
4. 更新 `TokenUsage.__add__()` 累加新增字段。
5. 更新 `TokenUsage.to_dict()` / `from_dict()`，兼容旧 session YAML。
6. 更新 OpenAI-compatible usage 解析。
7. 更新 Claude usage 解析。
8. ClaudeAdapter 支持 cache_control。
9. OpenAI-compatible adapter 默认不注入未知 `cache_control`。

### 验证

新增测试：

- `tests/test_cache_control.py`

覆盖：

- TokenUsage 新字段序列化/反序列化。
- Usage 累加正确。
- OpenAI-compatible usage 字段存在时能解析。
- Claude usage 字段存在时能解析。
- provider 不支持缓存字段时不报错。

---

## Task 8: 实现 Plan Mode reminder 编排

### 目标

Plan Mode 文本不拼进 System Prompt，而是按轮次通过 system-reminder 注入。

### 文件影响

新增：

- `src/mewcode/engine/prompt/plan_mode.py`

修改：

- `src/mewcode/tui/app.py`
- `src/mewcode/tui/widgets/status_bar.py`（如需显示 Plan 状态）
- `src/mewcode/tui/widgets/input_box.py`（如已有模式切换相关逻辑需要配合）

### 步骤

1. 定义 `PlanModeReminder` 或等价管理器。
2. 保存 Plan Mode 用户轮次计数。
3. 进入 Plan Mode：
   - 计数置为 1。
   - 当前轮注入完整版 reminder。
4. 后续 Plan Mode 用户轮次：
   - 第 6、11、16... 轮注入完整版。
   - 其他轮次注入轻量 reminder 或不注入。
5. 退出 Plan Mode：
   - 清空计数。
   - 停止注入 Plan Mode reminder。
6. 当前 TUI 的 `mode` 只有 Chat / Single：
   - 若本章实现真实 Plan Mode，则新增 `Plan` mode。
   - 若保守处理，则先完成 backend 编排测试，TUI 接入留最小实现。

### 验证

新增测试：

- `tests/test_plan_mode.py`

覆盖：

- 第 1 轮完整版。
- 第 2-5 轮轻量版或无注入。
- 第 6 轮完整版。
- 第 11 轮完整版。
- 退出后不再注入。
- system_text 不包含 Plan Mode 文本。

---

## Task 9: 增加典型场景评估脚本

### 目标

提供 5 个人工评估场景，用于每次修改 Prompt 后对照行为。

### 文件影响

新增：

- `tests/eval_prompts.py`

### 步骤

1. 定义场景数据结构：
   - name
   - input
   - setup
   - expected_behavior
   - manual_checkpoints
2. 实现场景 1：长会话缓存命中。
3. 实现场景 2：环境上下文变化。
4. 实现场景 3：Plan Mode 注入。
5. 实现场景 4：工具选择。
6. 实现场景 5：未来动态源预留。
7. 脚本输出 Markdown 或纯文本报告，方便人工对照。

### 验证

- `python tests/eval_prompts.py` 能输出 5 个场景。
- 不依赖真实 LLM API。
- 不修改项目文件。

---

## Task 10: 更新集成路径和兼容性

### 目标

把新 Prompt 体系接入现有 Agent Loop，同时保持旧测试通过。

### 文件影响

修改：

- `src/mewcode/tui/app.py`
- `src/mewcode/engine/agent.py`（如需要传入 payload 对象）
- `src/mewcode/engine/models/client.py`（如需要暴露 cache 能力）
- `src/mewcode/engine/tools/system_prompt.py`

### 步骤

1. 保持 `run_agent_loop()` 的当前签名尽量不变：
   - `build_messages` 仍返回 `list[Message]`
   - `tools_payload` 仍从外部传入
2. 在 TUI 层负责调用 assembler：
   - 构造 sections
   - 构造 env_context
   - 收集 reminders
   - 构造 tools payload
3. 将 `system_text` 包装成 `MessageRole.SYSTEM`，拼到 messages 前面，兼容现有 adapter。
4. 确保临时注入消息不进入 `ConversationManager`。
5. 确保工具调用 loop 后续请求仍能重新组装最新 messages，但 system_text/tools 保持稳定。

### 验证

- 现有 Agent Loop 测试通过。
- 现有 adapter 测试通过。
- TUI 能正常发起一次请求。
- 工具调用流程仍能执行多轮。

---

## Task 11: 更新 CHANGELOG

### 目标

开发完成和验收后记录本章变更。

### 文件影响

修改：

- `CHANGELOG.md`

### 步骤

1. 增加 Chapter 05 Prompt System 条目。
2. 记录：
   - 七模块 System Prompt。
   - assembleAPIPayload。
   - environment-context 迁移。
   - system-reminder。
   - Prompt Cache usage。
   - Plan Mode reminder。
   - 评估脚本。

### 验证

- CHANGELOG 条目能让后续 coding agent 理解本章改动范围。
