# Claude Code 能力覆盖路线 Tasks

> 进度规则：`[ ]` 未开始，`[-]` 进行中，`[x]` 已验证完成，`[!]` 阻塞。每个任务完成后记录验证命令与结果；不得以“已实现但未验证”标记完成。

## 当前状态

- 阶段：实施中（P0）
- 当前实施任务：T8 引入 ProjectRuntime 与上下文预算模型
- 已批准文档：`spec.md`、`plan.md`、`task.md`、`checklist.md`
- 待批准文档：无
- 实现代码：尚未开始
- 已知环境问题：当前 Python 环境未安装 `textual` 与 `pytest-asyncio`，完整测试套件无法收集；在 T1 前先恢复可测试环境。

## 文件清单

| 操作 | 文件或目录 | 职责 |
|---|---|---|
| 修改 | `config.yaml`、`config.py` | 安全、上下文、扩展、MCP、编排配置与安全默认值 |
| 修改 | `engine/tools/base.py`、`registry.py`、现有工具 | 工具风险元数据、受控路径、网关接入 |
| 新建 | `engine/security/` | 权限策略、审批、审计、工作区与执行网关 |
| 修改 | `engine/agent.py`、`agent_events.py`、`conversation.py` | 受控工具执行、事件、上下文快照、会话元数据 |
| 新建 | `engine/context/` | token 预算、上下文规划、压缩、项目记忆 |
| 新建 | `engine/extensions/` | Skill、Slash Command、Hook 目录与运行器 |
| 新建 | `engine/mcp/` | MCP 服务管理、客户端与工具适配 |
| 新建 | `engine/orchestration/` | 子任务、Worktree、团队与变更审查 |
| 修改 | `tui/app.py`、`tui/widgets/`、`cli.py` | 审批交互、状态呈现、命令与项目运行时组装 |
| 新建/修改 | `tests/test_security_*.py`、`test_context_*.py`、`test_extensions_*.py`、`test_mcp_*.py`、`test_orchestration_*.py`、既有 TUI 测试 | 单元、集成、拒绝路径与端到端覆盖 |
| 修改 | `.gitignore`、配置示例、`CHANGELOG.md` | 密钥治理、迁移说明和交付记录 |

## P0：交付准备与安全基线

### T1: 恢复可重复的测试环境

**状态：** `[ ]`  
**依赖：** 无  
**文件：** `pyproject.toml`、开发说明（仅在发现缺失时修改）

1. 使用项目声明的开发依赖创建或选择隔离 Python 环境。
2. 安装运行依赖和 `dev` 依赖，使 Textual 与 asyncio 测试插件可用。
3. 运行完整现有测试套件，记录基线结果；若存在既有失败，将其与本路线变更分开记录。
4. 确认测试命令、Python 版本和依赖安装方式可由后续任务复用。

**验证：** `python -m pytest tests -q` 可完成收集；结果记录在本任务文档的进度日志。

### T2: 移除已提交密钥并建立安全配置基线

**状态：** `[ ]`  
**依赖：** T1  
**文件：** `config.yaml`、`.gitignore`、配置文档、相关测试

1. 将示例或默认配置中的认证信息改为环境变量引用或非敏感占位值。
2. 增加本地私有配置的忽略规则与安全加载约定。
3. 保持已有环境变量覆盖行为，并在缺少必要凭据时给出安全、可理解的报错。
4. 添加配置测试，证明密钥不会被示例配置或审计输出泄露。

**验证：** 配置测试通过；仓库跟踪文件扫描不包含真实凭据；使用环境变量仍可创建模型配置。

## P1：权限、审批、审计与工作区隔离

### T3: 定义统一执行请求、权限结果与工具风险元数据

**状态：** `[ ]`  
**依赖：** T1、T2  
**文件：** 新建 `engine/security/models.py`；修改 `engine/tools/base.py`、`engine/tools/registry.py`

1. 定义操作类别、风险等级、执行请求、权限结果、授权范围和审计条目的领域模型。
2. 为现有六个工具声明准确的读写、命令、资源与并发元数据。
3. 保持 ToolRegistry 的模型协议输出兼容，并让其能接受统一执行请求。
4. 编写数据模型和工具元数据的序列化、默认值与兼容性测试。

**验证：** 单元测试证明六工具均有确定风险分类，旧的工具调用测试仍通过。

### T4: 实现工作区路径边界和资源预览

**状态：** `[ ]`  
**依赖：** T3  
**文件：** 新建 `engine/security/workspace.py`；修改文件工具与 `ToolContext`

1. 规范化工作区根目录、请求路径和符号链接目标。
2. 拒绝工作区外的绝对路径、相对路径逃逸和符号链接逃逸。
3. 为读写、编辑、搜索操作生成资源摘要；为写入和编辑生成变更摘要与 diff 预览数据。
4. 保留正常项目内相对和绝对路径的支持。

**验证：** 临时目录测试覆盖项目内访问、`..` 逃逸、绝对路径逃逸和链接逃逸；文件工具既有测试通过。

### T5: 实现权限策略、授权存储和审批等待

**状态：** `[x]`  
**依赖：** T3、T4  
**文件：** 新建 `engine/security/policy.py`、`approval.py`；修改 `config.py`、`config.yaml`

1. 实现默认策略：只读允许，写入、命令、外部服务和管理操作需审批。
2. 实现单次、会话与项目级许可的创建、匹配、撤销和到期规则。
3. 将策略结果转换为可等待、可取消的审批请求。
4. 为许可扩张、项目切换、审批拒绝和超时编写拒绝路径测试。

**验证：** 策略测试证明任何临时许可均不跨项目生效，写入和 Bash 默认进入待审批状态。

### T6: 接入执行网关、审计与 Agent 事件

**状态：** `[x]`  
**依赖：** T4、T5  
**文件：** 新建 `engine/security/gateway.py`、`audit.py`；修改 `engine/agent.py`、`agent_events.py`、`conversation.py`

1. 建立“预览—判定—审批—执行—审计”的唯一工具调用流程。
2. 让 Agent Loop 将所有工具调用交给网关，并在批准后按原有顺序继续模型循环。
3. 增加审批、拒绝、执行与审计事件，确保取消不遗留未完成调用。
4. 持久化审计摘要，避免写入原始敏感输入或密钥。

**验证：** 假工具的集成测试证明允许、拒绝、取消和工具失败都能返回模型可处理的结果，并生成审计条目。

### T7: 完成审批与审计的 TUI 交互

**状态：** `[x]`  
**依赖：** T6  
**文件：** 修改 `tui/app.py`、`tui/widgets/chat_area.py`、`status_bar.py`；新增所需 widget 与测试

1. 在聊天区域展示操作摘要、风险、diff 摘要和授权选项。
2. 将用户审批决定回传给当前 ProjectRuntime，并在拒绝或取消后恢复输入状态。
3. 展示最近审计结果与待审批数，不泄露敏感数据。
4. 编写 Textual 测试覆盖批准、拒绝、超时和 Esc 取消。

**验证：** TUI 测试可模拟一次写文件审批并观察到批准后执行、拒绝后不执行。

## P2：上下文预算与项目记忆

### T8: 引入 ProjectRuntime 与上下文预算模型

**状态：** `[ ]`  
**依赖：** T6  
**文件：** 新建 `engine/runtime.py`、`engine/context/models.py`、`budget.py`；修改 `tui/app.py`、`engine/agent.py`

1. 建立按工作区隔离的 ProjectRuntime，并接入权限与会话状态。
2. 定义 ContextItem、ContextPlan 与 token 预算模型。
3. 为系统提示、近期消息、工具结果、记忆和扩展指令定义默认优先级与预算。
4. 让 Agent 在每次模型调用前获得不可变 ContextPlan。

**验证：** 单元测试验证预算计算、优先级截断和不同工作区的运行时隔离。

### T9: 实现可追溯上下文压缩与会话集成

**状态：** `[ ]`  
**依赖：** T8  
**文件：** 新建 `engine/context/planner.py`、`compression.py`；修改 `conversation.py`、`agent.py`

1. 在预算接近上限时选择低优先级历史进行压缩，并记录摘要来源。
2. 失败时保持原始消息可用并返回降级状态，不丢失会话。
3. 让 ConversationManager 保存摘要和上下文元数据，同时兼容旧 YAML 会话。
4. 在 Agent 事件中暴露 ContextPlan 摘要。

**验证：** 伪 LLM 测试证明压缩触发、失败降级、来源追溯和旧会话加载兼容。

### T10: 实现项目记忆与上下文可见性

**状态：** `[ ]`  
**依赖：** T8、T9  
**文件：** 新建 `engine/context/memory.py`；修改 TUI、CLI、配置和测试

1. 提供项目记忆的保存、列出、更新、删除与选择性加载。
2. 将记忆作为来源明确的 ContextItem 纳入计划。
3. 在界面或命令中显示当前 ContextPlan 的组成、预算和排除项。
4. 测试项目间读取拒绝、删除后不加载与记忆来源展示。

**验证：** 端到端测试创建两个临时项目，确认记忆只在所属项目的新会话中加载。

## P3：Skill、Slash Command 与 Hook

### T11: 实现扩展目录与声明校验

**状态：** `[ ]`  
**依赖：** T8、T10  
**文件：** 新建 `engine/extensions/models.py`、`catalog.py`；修改配置与测试

1. 定义 Skill、命令和 Hook 的声明、来源、作用域、权限和启用状态。
2. 扫描应用级与项目级扩展位置，检测无效声明与重复名称。
3. 默认禁用未信任或配置无效的扩展，并在 UI 中显示原因。
4. 建立目录加载和作用域隔离测试。

**验证：** 测试可加载有效扩展、拒绝重复/无效定义，并能列出来源与状态。

### T12: 迁移 Slash Command 并实现 Skill 执行

**状态：** `[ ]`  
**依赖：** T11、T6  
**文件：** 新建 `engine/extensions/commands.py`、`skills.py`；修改 `tui/app.py`、`input_box.py` 与测试

1. 将现有硬编码命令注册到统一目录，保持既有使用方式。
2. 将命令补全从常量迁移为目录查询。
3. 让 Skill 将其说明和允许操作加入 ContextPlan，并通过网关运行声明步骤。
4. 展示命令与 Skill 的来源、开始、结束、失败与审计关联。

**验证：** 兼容性测试覆盖全部现有命令；Skill 集成测试证明受控工具操作需要相同审批。

### T13: 实现 Hook 生命周期与失败策略

**状态：** `[ ]`  
**依赖：** T11、T12  
**文件：** 新建 `engine/extensions/hooks.py`；修改 Agent、网关、TUI 与测试

1. 定义会话、任务、工具与子任务的可用 Hook 时机。
2. 执行 Hook 时建立来源清晰的 ExecutionRequest。
3. 支持非阻断、阻断和失败报告策略，且所有失败可见。
4. 通过配置禁用 Hook 或限制其作用域。

**验证：** 集成测试验证成功 Hook、非阻断失败、阻断失败、审批拒绝与取消行为。

## P4：MCP 外部工具

### T14: 实现 MCP 服务配置和生命周期管理

**状态：** `[ ]`  
**依赖：** T6、T11  
**文件：** 新建 `engine/mcp/config.py`、`manager.py`、`client.py`；修改配置、运行时与测试

1. 定义按项目作用域配置的服务标识、连接方式、超时与启用状态。
2. 实现启动/连接、初始化、关闭、失败隔离和状态查询。
3. 不记录服务密钥或完整敏感环境变量到日志和审计。
4. 使用伪服务测试连接失败、超时、禁用和重试。

**验证：** 服务管理测试证明一个失败服务不会阻止本地工具或其他服务继续可用。

### T15: 将 MCP 工具适配到受控工具网关

**状态：** `[ ]`  
**依赖：** T14、T6  
**文件：** 新建 `engine/mcp/adapter.py`；修改 ToolRegistry、Agent、TUI 与测试

1. 将远端工具描述映射为具有服务来源和风险元数据的标准 Tool。
2. 将调用交给 Security Gateway，展示服务、输入和结果摘要。
3. 将协议、参数、超时与远端错误转换为可恢复的 ToolResult。
4. 在服务禁用或断连时撤销其可用工具。

**验证：** 伪 MCP 服务端到端测试覆盖发现、审批后调用、拒绝、超时和断连。

## P5：SubAgent 与 Git Worktree

### T16: 实现子任务运行时、最小上下文和权限投影

**状态：** `[ ]`  
**依赖：** T8、T6、T15  
**文件：** 新建 `engine/orchestration/tasks.py`；修改 Agent、事件、运行时、TUI 与测试

1. 定义 TaskSpec、TaskRun、状态流转、取消与产物。
2. 为子任务创建独立会话、ContextPlan、审计链和权限上限。
3. 限制子任务不能自行扩大主任务许可或读取未投影的记忆。
4. 向主任务呈现状态、结果与失败原因。

**验证：** 两个并行伪子任务测试证明状态独立，低权限子任务无法执行主任务已许可的高风险操作。

### T17: 实现受管 Git Worktree 与变更审查

**状态：** `[ ]`  
**依赖：** T16  
**文件：** 新建 `engine/orchestration/worktrees.py`、`merge_review.py`；修改配置、TUI 与测试

1. 验证 Git 工作区，创建并登记任务专属 WorktreeLease。
2. 提供状态、diff、冲突和清理检查，避免删除非受管目录。
3. 将变更摘要交给用户批准采纳或拒绝；不自动覆盖主工作区。
4. 为非 Git 项目、创建失败、脏工作区和冲突增加可理解的降级行为。

**验证：** 临时 Git 仓库端到端测试完成创建、修改、diff 审查、拒绝采纳和安全清理。

## P6：Agent Teams

### T18: 实现团队定义、分派与状态汇总

**状态：** `[ ]`  
**依赖：** T16、T17  
**文件：** 新建 `engine/orchestration/teams.py`；修改 TUI、CLI、配置与测试

1. 定义团队角色、成员、任务队列、依赖和资源上限。
2. 通过 TaskRunner 分派工作，不直接执行工具或修改文件。
3. 汇总成员进度、输出、审计引用与待处理采纳项。
4. 限制并发数，并检测相同目标文件或工作树的潜在冲突。

**验证：** 双角色模拟团队测试证明依赖顺序、状态汇总、并发上限和冲突提示正确。

### T19: 完成团队交付、回归与文档更新

**状态：** `[ ]`  
**依赖：** T18  
**文件：** `README.md`、`MANUAL.md`、`CHANGELOG.md`、全部测试与本进度文档

1. 编写用户可见的权限、MCP、扩展、记忆、子任务和团队操作说明。
2. 运行完整测试、兼容性测试和所有阶段验收场景。
3. 将每个任务的真实验证命令和结果回填至本文件的进度日志。
4. 在 CHANGELOG 中记录版本、破坏性变更、迁移步骤与安全默认值。

**验证：** 完整测试通过；文档中的关键工作流至少各有一个验证过的端到端场景。

## 执行顺序

```text
T1 → T2 → T3 → T4 → T5 → T6 → T7
                           └→ T8 → T9 → T10
                                      └→ T11 → T12 → T13
                                              └→ T14 → T15
                                                      └→ T16 → T17 → T18 → T19
```

在同一阶段内，仅在依赖任务验证完成后并行：T9 与部分 T10 准备工作可并行；T13 在 T12 稳定后执行；MCP、子任务和团队实现严格按安全边界成熟度顺序推进。

## 进度日志

| 日期 | 任务 | 状态 | 验证证据 | 备注 |
|---|---|---|---|---|
| 2026-08-24 | 文档阶段：Spec | `[x]` | 用户已明确批准 | 不含实现代码 |
| 2026-08-24 | 文档阶段：Plan | `[x]` | 用户已明确批准 | 不含实现代码 |
| 2026-08-24 | 文档阶段：Tasks | `[x]` | 用户已明确批准 | 不含实现代码 |
| 2026-08-24 | 文档阶段：Checklist | `[x]` | 用户已明确批准 | 不含实现代码 |
| 2026-08-24 | T1 | `[x]` | `python -m pip install -e ".[dev]"`; `python -m pytest tests -q` 全量通过 | 测试命令需使用允许写入系统临时目录的环境 |
| 2026-08-24 | T2 | `[x]` | `python -m pytest tests/test_config_env.py tests/test_config_local.py -q`：7 passed | 明文凭据已移除；本地覆盖配置已忽略 |
| 2026-08-24 | T3 | `[x]` | `python -m pytest tests/test_security_models.py tests/test_tools_base.py -q`：12 passed | 已定义执行请求、权限结果、操作/风险枚举与六工具元数据 |
| 2026-08-24 | T4 | `[x]` | `python -m pytest tests/test_tools_base.py tests/test_tools_read_file.py tests/test_tools_write_file.py tests/test_tools_edit_file.py -q`：41 passed | 工作区边界、越界拒绝与资源预览接口已完成 |
| 2026-08-24 | T5 | `[x]` | `python -m pytest tests/test_security_models.py tests/test_security_policy.py tests/test_security_approval.py tests/test_security_gateway.py tests/test_security_audit.py tests/test_security_config.py tests/test_config_local.py tests/test_tools_base.py tests/test_tools_read_file.py tests/test_tools_write_file.py tests/test_tools_edit_file.py tests/test_tools_bash.py tests/test_tools_glob.py tests/test_tools_grep.py -q -p no:cacheprovider --basetemp .tmp_pytest\\t5-security`：90 passed | 默认只读放行；一次性、会话、项目授权均可撤销，项目切换、超时与取消均拒绝且不遗留待审请求。 |
| 2026-08-24 | T6 | `[x]` | `python -m pytest tests/test_security_approval.py tests/test_security_gateway.py tests/test_security_agent_gateway.py tests/test_security_audit.py tests/test_agent_loop.py tests/test_agent_events.py -q -p no:cacheprovider --basetemp .tmp_pytest\\t6-verify`：20 passed | 同一 Agent 循环在批准后继续；拒绝、超时和取消均不执行工具，并写入脱敏审计记录。 |
| 2026-08-24 | T7 | `[x]` | `python -m pytest tests/test_tui_agent_loop.py tests/test_tui_metrics.py tests/test_tui_tool_flow.py tests/test_tui_tool_trace.py tests/test_tui_ui_layout.py tests/test_tui_security_approval.py -q -p no:cacheprovider --basetemp .tmp_pytest\\t7-tui`：29 passed | 审批卡片显示安全摘要与授权选项；`/audit` 只展示最近的脱敏决策摘要。 |
