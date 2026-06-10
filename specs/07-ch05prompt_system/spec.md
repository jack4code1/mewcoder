# Chapter 05 Prompt System Spec

## 背景

MewCode 当前的 System Prompt 仍然偏向零散拼接。静态规则、环境上下文、Plan Mode 指令以及动态提醒混在同一条 system 内容中，会导致两个问题：

1. Prompt 结构不清晰，后续扩展项目指令、记忆、MCP、Skill 等动态上下文时缺少稳定边界。
2. System Prompt 频繁变化会破坏 Prompt Cache，使长任务中的 input token 成本无法有效下降。

本章要把 Prompt 体系从“拼接字符串”升级为“静态 System Prompt + 动态 messages 注入 + 工具通道”的三通道组装模型。

## 目标

本章完成一套完整的 Prompt 工程体系设计，使 MewCode 具备以下能力：

1. System Prompt 拥有清晰的七模块结构：
   - Identity
   - Behavior
   - Tool Usage
   - Code Quality
   - Security
   - Task Pattern
   - Output Style

2. Prompt 组装管线能够把七类信息正确分发到三个 API 通道：
   - `system`
   - `messages`
   - `tools`

3. 环境上下文从 system 通道移出，作为 messages 中的首条 user 消息注入，避免污染 System Prompt 缓存。

4. 工具描述得到强化，使模型能更稳定地区分并组合使用：
   - ReadFile
   - EditFile
   - WriteFile
   - Bash
   - Glob
   - Grep

5. Prompt Cache 控制成为一等设计目标：
   - 静态 System Prompt 保持稳定。
   - tools 通道保持稳定。
   - 动态信息进入 messages。
   - 支持缓存的 provider 可以观察 usage 中的缓存命中信息。
   - 不支持缓存的 provider 应保持兼容并明确降级。

6. 引入 `system-reminder` 机制：
   - 它是 messages 中的特殊 user 消息。
   - 内容用 `<system-reminder>...</system-reminder>` 包裹。
   - 模型应把它理解为系统补充指令，而不是普通用户对话。
   - 它用于承载动态上下文，避免修改 System Prompt。

7. Plan Mode 改为通过 `system-reminder` 注入：
   - 不再拼接进 System Prompt。
   - Plan Mode 开启后的第 1 个用户轮次注入完整版说明。
   - 此后每 5 个 Plan Mode 用户轮次重复注入完整版。
   - 其余轮次可以注入轻量提醒或不注入。

8. 提供 5 个典型场景评估脚本，方便人工对比 Prompt 修改前后的行为。

## 七源定义

Prompt 组装管线面向以下七类信息源：

1. 静态 System Prompt  
   角色设定、行为准则、安全边界、输出风格等七模块内容。

2. 环境上下文  
   工作目录、操作系统、当前时间、Git 状态等运行时信息。

3. 工具描述  
   每个工具的 JSON Schema 和 description 字段。

4. 项目指令文件  
   `MEWCODE.md` 中的项目级 Agent 指令。本章只预留 source 类型和分发规则，不实现加载。

5. 自动记忆  
   Agent 自动提取的用户偏好和项目知识。本章只预留 source 类型和分发规则，不实现提取。

6. System Reminder  
   MCP Server、Skill、Plan Mode、温和提醒等动态补充指令。

7. 对话历史  
   已发生的 user / assistant / tool 消息。

## 三通道分发原则

### system

`system` 通道只承载稳定的静态 System Prompt 七模块内容。

它不应包含：

- 当前时间
- 工作目录
- Git 状态
- Plan Mode 文本
- MCP Server 状态
- Skill 列表
- MEWCODE.md 动态内容
- 自动记忆内容

### messages

`messages` 通道承载所有会话和运行时上下文，包括：

- 环境上下文
- 对话历史
- 当前用户输入
- `system-reminder`
- 未来的项目指令文件内容
- 未来的自动记忆内容

环境上下文应作为 messages 中靠前的 user 消息注入。

`system-reminder` 应使用 XML 标签包裹：

```xml
<system-reminder>
...
</system-reminder>
```

会话级 reminder 放在环境上下文之后、真实用户第一条消息之前。

轮次级 reminder 放在当前轮真实用户输入之前。

### tools

`tools` 通道承载工具 schema 和强化后的 description。

工具描述应说明：

- 工具适用场景
- 何时优先使用
- 与其他工具的配合关系
- 使用限制和风险
- 对文件读写、搜索、命令执行的安全边界

## Prompt Cache 期望

MewCode 应尽量让 `system` 和 `tools` 通道在多轮任务中保持稳定，以提高 Prompt Cache 命中率。

当 provider 支持缓存控制时，MewCode 应启用等价的临时缓存能力。

当 provider 返回 usage 中的缓存命中字段时，MewCode 应能读取并用于验证。

当 provider 不支持 Prompt Cache 或不返回命中字段时，MewCode 应保持请求兼容，并将缓存状态视为 unsupported，而不是错误。

## Plan Mode 行为

Plan Mode 是动态行为模式，不属于静态 System Prompt。

Plan Mode 指令通过 `system-reminder` 注入：

- 开启 Plan Mode 后的第 1 个用户轮次注入完整版。
- 第 6、11、16... 个 Plan Mode 用户轮次重复注入完整版。
- 其他 Plan Mode 轮次可以注入轻量提醒或不注入。
- 关闭 Plan Mode 后停止注入 Plan Mode reminder。

## 典型评估场景

本章提供 5 个用于人工评估的场景：

1. 长会话缓存命中  
   验证多轮任务中 system/tools 保持稳定，并能观察缓存命中或 unsupported 降级。

2. 环境上下文变化  
   验证时间、Git 状态等变化不会修改 system 通道。

3. Plan Mode 注入  
   验证 Plan Mode 指令通过 `system-reminder` 注入，而不是拼接进 System Prompt。

4. 工具选择  
   验证工具 description 能引导模型正确选择 ReadFile、Glob、Grep、EditFile、WriteFile、Bash。

5. 未来动态源预留  
   验证 MEWCODE.md、自动记忆、MCP/Skill 类内容能通过 messages/system-reminder 模型承载，不污染 system 通道。

## 非目标

本章不实现以下内容：

1. `MEWCODE.md` 项目指令文件加载。
2. 自动记忆系统。
3. 真实 MCP Server 接入。
4. LLM-as-judge 自动评估管线。
5. 新增真实 provider 的 Prompt Cache 专属协议，只定义抽象兼容模型。
