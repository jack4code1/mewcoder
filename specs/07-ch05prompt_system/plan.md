# Chapter 05 Prompt System Plan

## Current Evidence

### System Prompt (现状)

- `src/mewcode/engine/tools/system_prompt.py` 的 `build_system_prompt()` 产出一个扁平字符串，混合了角色设定、工作目录、OS、工具列表、工具使用指南和语言策略。
- `src/mewcode/tui/app.py` 的 `_messages_with_system()` 每次调用时重建 SYSTEM 消息，拼在 conversation messages 前面。
- 没有七模块结构，没有 Section 优先级排序。

### 消息组装 (现状)

- `app.py` 的 `build_messages` 闭包只做一件事：`[system_msg] + conversation_messages`。
- 环境上下文（working_dir、os_name、工具列表）写死在 system prompt 字符串里。
- 没有 `system-reminder` 注入点。
- 没有 Plan Mode 注入逻辑。

### 工具描述 (现状)

- 每个 Tool 子类的 `description` 字段已经包含 WHEN TO USE / WHEN NOT TO USE 基本指引。
- `registry.py` 的 `to_openai_format()` / `to_anthropic_format()` 直接使用 Tool.description。
- 描述质量可用但未涵盖工具间配合关系和优先级。

### Adapter 层 (现状)

- `CustomAdapter` / `OpenAIAdapter` / `OllamaAdapter`：通过 `_openai_protocol.py` 的 `convert_messages_to_openai()` 转换消息，SYSTEM role 直接传入 `{"role": "system", "content": ...}`。
- `ClaudeAdapter`：`_convert_messages()` 把 SYSTEM 消息抽出为 top-level `system` 字段。
- 没有 cache_control 注入点。
- `TokenUsage` 只有 `prompt_tokens` / `completion_tokens` / `total_tokens`，无 cache 命中字段。

## Architecture

### 核心改动

把当前 `build_system_prompt()` 扁平字符串 → 拆分为七模块 Section 对象；把当前 `_messages_with_system()` 单一拼接 → 拆分为三通道组装管线 `assembleAPIPayload()`。

### 新增模块

```text
src/mewcode/engine/prompt/
├── __init__.py
├── sections.py          # Section 基类 + 7 个 Section 子类
├── assembler.py         # assembleAPIPayload: 七源 → 三通道
├── cache_control.py     # Prompt Cache 抽象 + provider 降级
├── system_reminder.py   # SystemReminder 注入机制
└── plan_mode.py         # Plan Mode reminder 编排
```

### 修改模块

```text
src/mewcode/engine/tools/system_prompt.py
src/mewcode/tui/app.py
src/mewcode/engine/models/message.py
src/mewcode/engine/models/client.py
src/mewcode/engine/adapters/_openai_protocol.py
src/mewcode/engine/adapters/claude_adapter.py
src/mewcode/engine/adapters/custom_adapter.py
```

## Section 体系

### 基类

```python
@dataclass
class Section:
    """七模块 System Prompt 的一个区块。"""
    name: str
    priority: int
    content: str

    def render(self) -> str:
        """返回渲染后的文本块，带标题。"""
        ...
```

### 七个 Section

| Section | priority | 内容来源 |
| --- | ---: | --- |
| IdentitySection | 100 | 角色名、身份定位、核心使命 |
| BehaviorSection | 200 | 交互准则、安全边界、拒绝策略 |
| ToolUsageSection | 300 | 工具选型优先级、搜索→读取→编辑 流程、Bash 使用边界 |
| CodeQualitySection | 400 | 代码风格、重构原则、测试要求 |
| SecuritySection | 500 | 文件操作权限、命令执行白名单/黑名单、敏感信息处理 |
| TaskPatternSection | 600 | 多步任务分解、Plan Mode 提示、复杂任务管理 |
| OutputStyleSection | 700 | 语言策略、输出格式、Markdown 渲染约束 |

### 组装规则

1. 按 `priority` 升序排列所有 Section。
2. 每个 Section 渲染为 `## {name}\n\n{content}\n\n`。
3. 拼接后作为 system 通道的唯一内容。
4. system 通道在整个会话期间保持不变（除非用户手动修改 Section 内容）。

## assembleAPIPayload 管线

### 函数签名

```python
@dataclass
class AssembledPayload:
    """组装后的三通道输出。"""
    system_text: str
    messages: list[Message]
    tools: list[dict]
    cache_config: CacheConfig

def assembleAPIPayload(
    sections: list[Section],
    registry: ToolRegistry,
    conversation_messages: list[Message],
    env_context: EnvContext,
    reminders: list[SystemReminder],
    cache_config: CacheConfig,
) -> AssembledPayload:
    ...
```

### 七源 → 三通道分发规则

| 信息源 | 目标通道 | 说明 |
| --- | --- | --- |
| 静态 System Prompt | `system` | 七模块 Section 拼接，整个会话不变 |
| 环境上下文 | `messages` | 首条 user 消息，用 `<environment-context>` 包裹 |
| 工具描述 | `tools` | registry 格式化输出，description 已强化 |
| 项目指令文件 | `messages` | system-reminder 注入（本章预留接口，不实现加载） |
| 自动记忆 | `messages` | system-reminder 注入（本章预留接口，不实现提取） |
| System Reminder | `messages` | role=user + `<system-reminder>` XML 包裹 |
| 对话历史 | `messages` | 原样传入 user/assistant/tool 消息 |

### messages 通道最终顺序

```text
[0] user: <environment-context>Working directory: /path...Host OS: windows...</environment-context>
[1] user: <system-reminder>会话级动态说明...</system-reminder>  (如果存在)
[2..N] 历史 user / assistant / tool 消息
[N+1] user: <system-reminder>当前轮动态说明...</system-reminder>  (如果存在)
[N+2] user: 用户当前输入
```

## 环境上下文重构

### 当前实现

```python
"Working directory: {ctx.working_dir}\n"
"Host OS: {ctx.os_name}\n"
```

混合在 system prompt 里，每次请求都会重建。

### 目标实现

环境上下文作为独立的 user 消息，用 XML 标签包裹：

```xml
<environment-context>
Working directory: E:\agent_class\project
Host OS: windows
Current time: 2026-06-11 14:30:00 CST
Git branch: main (3 files modified)
</environment-context>
```

- 放在 messages 数组的第一位。
- 包含 current_time 和 git_status。
- 不进入 system 通道，不污染缓存。

## 工具描述强化

对 6 个核心工具的 description 字段补充以下信息：

### ReadFile

- 已有：WHEN TO USE / NOT TO USE / PATH / PAGING / RETURN FORMAT
- 补充：与 Glob/Grep 的配合关系（先搜索定位再读取）

### EditFile

- 已有：WHEN TO USE / NOT TO USE / old_string 唯一性规则 / 预览格式
- 补充：与 ReadFile 的强制配合（编辑前必须先读取）

### WriteFile

- 已有：WHEN TO USE / NOT TO USE / PATH / ENCODING
- 补充：与 EditFile 的选择原则（小改动用 EditFile，大面积重写用 WriteFile）

### Bash

- 已有：WHEN TO USE / NOT TO USE / STREAMS / TIMEOUT / OUTPUT / EXIT CODE
- 补充：文件操作优先用专用工具，Bash 只做工具无法覆盖的操作

### Glob

- 已有：WHEN TO USE / NOT TO USE / PATTERN / EXCLUDED / RESULT FORMAT
- 补充：与 ReadFile 的典型组合模式

### Grep

- 已有：WHEN TO USE / NOT TO USE / PATTERN / include / context / OUTPUT FORMAT
- 补充：与 ReadFile 的典型组合模式，搜索内容 vs Glob 搜文件名

### 全局工具选型指引

写入 ToolUsageSection：

```text
工具选型优先级：
1. 搜索：Glob（文件名）→ Grep（内容）→ ReadFile（定位后读取）
2. 编辑：ReadFile → EditFile（小改动）| WriteFile（大面积重写/新文件）
3. 执行：专用工具优先，Bash 只做工具无法覆盖的操作（git、测试、构建等）
```

## Prompt Cache 控制

### 抽象模型

```python
@dataclass
class CacheConfig:
    """Prompt Cache 配置。"""
    provider_type: str
    system_ttl: str = "ephemeral"
    tools_ttl: str = "ephemeral"
    enabled: bool = True

@dataclass
class CacheUsage:
    """从 API 返回的缓存命中信息。"""
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_hit: bool = False
    supported: bool = True
```

### TokenUsage 扩展

```python
@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
```

### Adapter 适配

**CustomAdapter / OpenAIAdapter**:

- 在 tools payload 中不注入 `cache_control`（OpenAI-compatible 通常不支持此字段）。
- 从 usage 响应中提取 `cache_creation_input_tokens` / `cache_read_input_tokens`（如果存在）。
- 如果 provider 不返回这些字段，`CacheUsage.supported = False`。

**ClaudeAdapter**:

- system 通道：`payload["system"]` 改为 content block 格式，最后一个 block 附加 `{"type": "text", "text": ..., "cache_control": {"type": "ephemeral"}}`。
- tools 通道：每个 tool 定义附加 `{"cache_control": {"type": "ephemeral"}}`。
- 从 usage 中提取 `cache_creation_input_tokens` / `cache_read_input_tokens`。

### 降级策略

- 如果 adapter 不支持 cache_control 字段：不注入，标记 `supported=False`。
- 如果 provider 支持但当前请求未命中：正常返回，`cache_hit=False`。
- 所有降级情况不影响正常请求流程。

## system-reminder 注入机制

### 注入规则

| 类型 | 注入位置 | 生命周期 |
| --- | --- | --- |
| 会话级 | 环境上下文之后、第一条用户消息之前 | 整个会话有效 |
| 轮次级 | 当前轮用户输入之前、对话历史之后 | 仅当前轮 |

### 数据结构

```python
@dataclass
class SystemReminder:
    """一条 system-reminder 注入。"""
    content: str
    scope: str
    source: str
    priority: int = 100

def wrap_system_reminder(reminder: SystemReminder) -> str:
    """用 XML 标签包裹 reminder 内容。"""
    return f"<system-reminder>\n{reminder.content}\n</system-reminder>"
```

### 预留 source 类型

- `mcp`：MCP Server 上线/下线通知（本章不实现）
- `skill`：Skill 列表变化（本章不实现）
- `memory`：自动记忆注入（本章不实现）
- `project_doc`：MEWCODE.md 注入（本章不实现）
- `plan_mode`：Plan Mode 指令（本章实现）
- `custom`：其他自定义提醒

## Plan Mode 改造

### 当前实现

Plan Mode 不存在。`TaskPatternSection` 中只有静态提示。

### 目标实现

Plan Mode 的完整指令文本不再写进 System Prompt，而是通过 system-reminder 注入：

```python
class PlanModeReminder:
    """管理 Plan Mode 的 system-reminder 注入节奏。"""

    PLAN_FULL_TEXT = """You are in Plan Mode. Follow these rules:
- DO NOT write code, edit files, or execute commands.
- DO NOT create, modify, or delete any file.
- Your ONLY job: read files, ask questions, and produce a plan.
- Output format: a structured plan with numbered steps, file impacts, and verification criteria.
- After presenting the plan, ask the user: "Shall I proceed with implementation?"
- Only switch to execution mode after the user explicitly approves.
"""

    PLAN_LIGHT_TEXT = """[Plan Mode active - do not write code. Read and plan only.]"""
```

轮次计数口径：只统计 Plan Mode 开启后的用户轮次。第 1 轮注入完整版，第 6、11、16... 轮重复注入完整版。

## 典型场景评估脚本

在 `tests/eval_prompts.py` 中定义 5 个评估场景，每个场景包含输入、预期行为描述、人工检查点：

### 场景 1：长会话缓存命中

- 输入：连续 3 轮非工具任务
- 预期：第 2、3 轮 system_text 和 tools payload 与第 1 轮完全相同
- 检查点：assembleAPIPayload 输出的 system_text 可复现；如果有 cache hit 字段，验证第 2 轮起命中

### 场景 2：环境上下文变化

- 输入：第 1 轮 git branch=main，第 2 轮 git branch=dev
- 预期：system_text 不变，messages[0] 的 environment-context 内容变化
- 检查点：system 通道和 tools 通道保持稳定

### 场景 3：Plan Mode 注入

- 输入：开启 Plan Mode，连续 7 个用户轮次
- 预期：第 1 轮完整版、第 2-5 轮轻量版、第 6 轮完整版、第 7 轮轻量版
- 检查点：reminder 内容和注入位置正确，system_text 不含 Plan Mode 文本

### 场景 4：工具选择

- 输入：用户说“帮我找到所有 Python 测试文件，然后读取 test_agent.py”
- 预期：模型先调 Glob 找文件，再调 ReadFile 读取
- 检查点：工具调用顺序符合 description 中的指引

### 场景 5：未来动态源预留

- 输入：模拟一个 MCP Server 上线事件
- 预期：通过 system-reminder 注入 MCP 说明，system_text 不变
- 检查点：注入位置在 messages 中、格式为 `<system-reminder>` 包裹

## 测试策略

### 单元测试

- `tests/test_prompt_sections.py`：Section 排序、渲染、七模块完整性
- `tests/test_prompt_assembler.py`：assembleAPIPayload 输出结构、七源分发、messages 顺序
- `tests/test_system_reminder.py`：system-reminder 包裹格式、会话级/轮次级注入位置
- `tests/test_plan_mode.py`：Plan Mode 轮次计数、完整版/轻量版节奏
- `tests/test_cache_control.py`：CacheConfig 构建、TokenUsage 扩展字段解析、降级逻辑

### 集成测试

- `tests/test_prompt_integration.py`：assembleAPIPayload + registry + conversation 的端到端组装

### 评估脚本

- `tests/eval_prompts.py`：5 个定性场景，人工运行后对照输出

## Risks

- ClaudeAdapter 的 system 字段从字符串改为 content blocks 数组格式后，旧的单字符串路径需要兼容处理。
- CustomAdapter 的 cache_control 注入可能被不支持的 provider 忽略或报错，需要防御性处理。
- Plan Mode 轮次计数在并发或取消场景下可能不准确，需要在 on_plan_mode_exited 中强制重置。
- environment-context 消息的加入会增加每轮 prompt 长度，但因为不进入 system 通道，不影响缓存。
