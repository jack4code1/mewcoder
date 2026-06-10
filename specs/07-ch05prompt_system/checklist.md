# Chapter 05 Prompt System Checklist

## 文档与范围

- [ ] `spec.md` 明确描述本章目标：七模块 System Prompt、七源到三通道组装、Prompt Cache、system-reminder、Plan Mode 改造、评估脚本。
- [ ] `spec.md` 明确列出本章非目标：
  - 不实现 MEWCODE.md 加载。
  - 不实现自动记忆系统。
  - 不接入真实 MCP Server。
  - 不实现 LLM-as-judge 自动评估管线。
- [ ] `plan.md` 基于当前代码证据描述架构，不凭空假设不存在的模块。
- [ ] `task.md` 的每个任务都有文件影响、步骤和验证方式。
- [ ] `checklist.md` 的验收项均可通过代码检查、测试或人工评估观察。

## 七模块 System Prompt

- [ ] 存在 `Section` 结构，至少包含：
  - `name`
  - `priority`
  - `content`
  - `render()`
- [ ] 存在七个默认 Section：
  - `IdentitySection`
  - `BehaviorSection`
  - `ToolUsageSection`
  - `CodeQualitySection`
  - `SecuritySection`
  - `TaskPatternSection`
  - `OutputStyleSection`
- [ ] Section 按 `priority` 升序组装。
- [ ] System Prompt 输出稳定；相同 Section 输入多次组装结果完全一致。
- [ ] System Prompt 不包含动态环境信息：
  - 工作目录
  - 当前时间
  - Git 状态
  - Plan Mode 文本
  - MCP / Skill / MEWCODE / 自动记忆动态内容

## 七源到三通道组装

- [ ] 存在统一组装函数 `assembleAPIPayload` 或等价入口。
- [ ] 组装结果包含三个通道：
  - `system`
  - `messages`
  - `tools`
- [ ] 静态 System Prompt 只进入 `system` 通道。
- [ ] 环境上下文只进入 `messages` 通道。
- [ ] 工具 schema 和 description 只进入 `tools` 通道。
- [ ] 项目指令文件作为预留 source 类型存在，但本章不实现加载。
- [ ] 自动记忆作为预留 source 类型存在，但本章不实现提取。
- [ ] System Reminder 进入 `messages` 通道。
- [ ] 对话历史按原始 user / assistant / tool 顺序进入 `messages` 通道。
- [ ] 临时注入的 environment-context 和 system-reminder 不写入持久化会话历史。

## Environment Context

- [ ] 环境上下文从 system prompt 中移除。
- [ ] 环境上下文作为 messages 中靠前的 user 消息注入。
- [ ] 环境上下文使用 `<environment-context>...</environment-context>` 包裹。
- [ ] 环境上下文至少包含：
  - working directory
  - host OS
  - current time
  - git status 或明确 unavailable
- [ ] 环境上下文变化不会改变 system 通道内容。
- [ ] 环境上下文变化不会改变 tools 通道内容。

## Tools Description

- [ ] `ReadFile` description 说明：
  - 何时使用
  - 何时不使用
  - 与 Glob / Grep 的配合关系
  - 编辑前应先读取文件
- [ ] `EditFile` description 说明：
  - 适合小范围修改
  - 编辑前必须 ReadFile
  - `old_string` 必须唯一
  - 失败后应重新读取再尝试
- [ ] `WriteFile` description 说明：
  - 适合新文件或大面积重写
  - 不适合小范围修改
  - 小范围修改应使用 EditFile
- [ ] `Bash` description 说明：
  - 适合测试、构建、git、系统检查
  - 不应替代专用文件和搜索工具
  - 非零退出码不是工具错误，而是诊断信号
- [ ] `Glob` description 说明：
  - 用于按文件名或路径模式找文件
  - 不用于搜索文件内容
  - 找到文件后通常配合 ReadFile 或 Grep
- [ ] `Grep` description 说明：
  - 用于按内容搜索
  - 不用于按文件名找文件
  - 搜索结果后通常配合 ReadFile 阅读完整上下文

## Prompt Cache

- [ ] 存在 Prompt Cache 抽象配置。
- [ ] 支持 provider 能力差异：
  - 支持 cache_control 的 provider 可注入缓存控制。
  - 不支持的 provider 不注入未知字段。
  - 不支持缓存时标记 unsupported，不视为失败。
- [ ] Claude/Anthropic 语义下，system 通道可附加 `cache_control: { type: "ephemeral" }`。
- [ ] Claude/Anthropic 语义下，tools 通道可附加 `cache_control: { type: "ephemeral" }`。
- [ ] OpenAI-compatible 语义下，不默认注入可能导致报错的未知 cache_control 字段。
- [ ] `TokenUsage` 或等价 usage 模型能承载：
  - cache creation input tokens
  - cache read input tokens
- [ ] API 返回 usage 中存在缓存字段时，MewCode 能解析。
- [ ] API 不返回缓存字段时，请求流程正常，缓存状态视为 unsupported 或 0 命中。
- [ ] 长会话中 system/tools 内容稳定，具备命中 Prompt Cache 的条件。

## system-reminder

- [ ] 存在 `SystemReminder` 或等价结构。
- [ ] system-reminder 使用 `role=user` 注入 messages。
- [ ] system-reminder 内容使用 XML 标签包裹：

```xml
<system-reminder>
...
</system-reminder>
```

- [ ] 会话级 reminder 注入在 environment-context 之后、真实用户第一条消息之前。
- [ ] 轮次级 reminder 注入在当前轮真实用户输入之前。
- [ ] system-reminder 不拼入 System Prompt。
- [ ] system-reminder 不混写进真实用户正文。
- [ ] 支持预留 source：
  - `plan_mode`
  - `mcp`
  - `skill`
  - `memory`
  - `project_doc`
  - `custom`

## Plan Mode

- [ ] Plan Mode 文本不进入 System Prompt。
- [ ] Plan Mode 通过 system-reminder 注入。
- [ ] Plan Mode 轮次计数只统计 Plan Mode 开启后的用户轮次。
- [ ] 第 1 个 Plan Mode 用户轮次注入完整版。
- [ ] 第 6、11、16... 个 Plan Mode 用户轮次重复注入完整版。
- [ ] 其他 Plan Mode 用户轮次注入轻量提醒或不注入。
- [ ] 退出 Plan Mode 后停止注入 Plan Mode reminder。
- [ ] 取消请求或切换模式后，Plan Mode 计数不会污染后续普通 Chat 请求。

## 典型场景评估脚本

- [ ] 存在 `tests/eval_prompts.py` 或等价人工评估脚本。
- [ ] 脚本包含 5 个场景：
  - 长会话缓存命中
  - 环境上下文变化
  - Plan Mode 注入
  - 工具选择
  - 未来动态源预留
- [ ] 脚本不依赖真实 LLM API。
- [ ] 脚本不会修改项目文件。
- [ ] 脚本输出可人工检查的预期行为和检查点。
- [ ] Prompt 修改后可以重新运行脚本进行人工对比。

## 测试

- [ ] 新增或更新 Section 测试。
- [ ] 新增或更新 assembler 测试。
- [ ] 新增或更新 system-reminder 测试。
- [ ] 新增或更新 Prompt Cache usage 测试。
- [ ] 新增或更新 Plan Mode 测试。
- [ ] 新增或更新工具 description 测试。
- [ ] 现有 adapter 测试仍通过。
- [ ] 现有 Agent Loop 测试仍通过。
- [ ] 运行：

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/ -v
```

结果通过，或失败项有明确说明。

## CHANGELOG

- [ ] 开发和验收完成后更新 `CHANGELOG.md`。
- [ ] CHANGELOG 记录：
  - 七模块 System Prompt
  - assembleAPIPayload
  - environment-context 迁移
  - system-reminder
  - Prompt Cache usage
  - Plan Mode reminder
  - 评估脚本
