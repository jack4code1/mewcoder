# Claude Code 能力覆盖路线 Plan

## 架构总览

路线采用“统一执行边界，逐层扩展能力”的架构。既有 `ToolRegistry` 和 `run_agent_loop` 保持为模型调用工具的唯一入口；新增能力以适配器或编排层接入，不能绕过权限、审计、取消和事件流。

```text
Textual TUI / CLI commands
        │
Session + Project runtime
        ├── Command / Skill / Hook catalog
        ├── Context & Memory service
        └── Team coordinator
                │
            Agent runtime ── AgentEvent stream ── Chat / status UI
                │
            Tool execution gateway
          ┌─────┼───────────────┐
      Local tools  MCP tools  SubAgent / Worktree actions
          └─────┴───────────────┘
                │
      Permission policy + approval + audit ledger
```

按已批准的规格分六个可交付阶段实施：

1. 权限与审计基础：收口既有工具的工作区、风险、审批与审计边界。
2. 上下文预算与项目记忆：在安全边界内提供可追溯的上下文选择。
3. 可扩展自动化：建立 Skill、可注册命令和生命周期 Hook。
4. MCP：将外部服务映射为受控工具。
5. 隔离并行：提供 SubAgent 和 Git Worktree。
6. 团队协作：在子 Agent 能力之上编排 Agent Teams。

## 核心数据结构与接口

### 执行请求与风险判定

`Tool` 增加不可变的操作元数据：作用类型（只读、文件写入、命令、网络、外部服务、管理操作）、风险级别和可声明的资源范围。所有本地、MCP 和内部编排动作适配为同一执行请求。

`ExecutionRequest` 包含调用标识、来源（模型、用户、命令、Skill、Hook、子 Agent、MCP）、目标、输入、工作区、资源声明与父任务标识。

`PermissionDecision` 表示允许、拒绝或需要审批；携带原因、可选的许可范围和到期条件。只有网关可创建已允许的执行结果。

`ApprovalRequest` 为 UI 提供人类可读的操作摘要、风险说明、文件 diff（适用时）和三种授权范围：仅本次、当前会话、当前项目。拒绝与超时均产生明确的拒绝结果，而非异常。

`AuditEntry` 记录请求、判定、审批选择、结果状态、持续时间、调用来源和资源摘要；敏感输入内容不以明文重复写入审计记录。

### 上下文、记忆与项目运行时

`ProjectRuntime` 以规范化工作区根目录为键，持有本项目的权限状态、上下文预算、记忆仓库、已启用扩展和运行中任务。它取代分散的全局可变状态。

`ContextItem` 用统一格式表示系统提示、当前会话、压缩摘要、项目记忆、Skill 指令和工具结果；包含来源、优先级、估算 token、可见性与是否可压缩。

`ContextPlan` 是每次模型调用前创建的快照，包含纳入项、排除项、预算使用量和压缩说明。用户可从 UI 查询该快照。

`MemoryRecord` 包含项目作用域、类型（事实、偏好、决策）、内容、来源、创建与更新时间。项目根目录是强制隔离键；跨项目读取直接失败。

### 扩展目录

`SkillDefinition`、`CommandDefinition` 和 `HookDefinition` 均带有名称、来源路径、项目作用域、说明、输入契约、所需权限和启用状态。

`ExtensionCatalog` 负责加载、校验、查找和列出扩展；`SkillRunner` 与 `HookRunner` 只通过执行网关执行其声明的动作。Hook 结果使用结构化状态上报，阻断型 Hook 必须显式声明。

### MCP 与多 Agent

`McpServerConfig` 定义服务标识、启动/连接方式、启用状态、超时和项目作用域。`McpClient` 负责生命周期、工具发现和协议通信；`McpToolAdapter` 将远端工具转为标准 `Tool`，并保留服务来源。

`TaskSpec` 定义子任务目标、输入上下文选择、权限上限、隔离要求和预期交付物。`TaskRun` 记录状态、事件、产物、审计关联与失败原因。

`WorktreeLease` 记录由系统创建的工作树路径、基线提交、分支、所属任务和清理状态。合并或采用改动始终由用户确认。

`TeamDefinition` 定义成员角色与任务；`TeamCoordinator` 只负责分派、状态汇总、依赖顺序与冲突呈现，不直接绕过子任务的权限网关。

## 模块设计

### 权限、审批与审计模块

新增 `engine/security/`：

- `policy.py`：根据工具元数据、工作区、来源和已授予许可计算 `PermissionDecision`。
- `approval.py`：管理待审批请求、会话/项目授权及撤销。
- `audit.py`：持久化和查询 `AuditEntry`。
- `workspace.py`：解析工作区和路径包含关系，拒绝绝对路径逃逸与符号链接逃逸。
- `gateway.py`：唯一工具执行入口；执行“资源预览 → 策略判定 → 审批 → 调用 → 审计”的固定流程。

`ToolContext` 改为持有已验证的工作区信息；文件工具不再自行决定路径边界。`BashTool` 仍执行命令，但其风险、命令摘要和审批由网关控制。`AgentEvent` 增加审批等待、批准、拒绝和审计引用事件，TUI 渲染待处理操作并接收用户决定。

### 上下文与记忆模块

新增 `engine/context/`：

- `budget.py`：估算并分配各类上下文的 token 预算。
- `planner.py`：为每个模型请求生成 `ContextPlan`，按优先级选择内容。
- `compression.py`：调用现有 LLM 接口生成受标记的会话摘要；失败时保留原始消息并报告降级。
- `memory.py`：保存、查询、更新和删除项目隔离的记忆。

`ConversationManager` 保持会话持久化职责，但提供读取、摘要替换和元数据访问接口。Agent 在每轮请求前向 Context Planner 请求消息快照，而不是无界地发送完整历史。

### Skill、命令与 Hook 模块

新增 `engine/extensions/`：

- `catalog.py`：扫描应用级与项目级扩展，校验唯一名称和声明。
- `skills.py`：将 Skill 说明和允许的操作加入 Context Plan，并执行其步骤。
- `commands.py`：将 Slash Command 注册表接入 `InputBox` 补全与应用命令分发。
- `hooks.py`：在会话、任务、工具与子任务生命周期触发 Hook，并以 `AgentEvent` 汇报。

现有硬编码命令迁移到同一命令注册表，保持 `/help`、`/save` 等兼容。Hook 的执行请求携带来源和声明权限，审批策略与普通工具一致。

### MCP 模块

新增 `engine/mcp/`：

- `config.py`：读取并验证服务配置。
- `client.py`：管理连接、初始化、发现、调用和关闭。
- `adapter.py`：生成带服务来源与风险元数据的 `McpToolAdapter`。
- `manager.py`：管理启用状态、服务错误隔离和工具注册同步。

MCP 工具注册到 `ToolRegistry` 前先通过 Manager 验证；调用仍交给 Security Gateway。初版只支持工具发现与调用，资源、提示模板及服务市场不在范围内。

### SubAgent、Worktree 与 Team 模块

新增 `engine/orchestration/`：

- `tasks.py`：创建、取消、追踪 `TaskRun`，并对上下文与权限做最小化投影。
- `worktrees.py`：调用 Git 创建、检查、比较和清理受管工作树。
- `teams.py`：维护团队角色、任务队列、依赖和汇总。
- `merge_review.py`：生成变更摘要和冲突报告，向 UI 发出用户采纳请求。

每个 SubAgent 使用独立 Conversation、ContextPlan、取消信号和任务审计链。并行数量通过统一资源限制配置控制。Worktree 仅用于 Git 工作区；无 Git 的项目可运行子任务但不提供隔离写入。

### TUI 与配置集成

`MewCodeApp` 创建 `ProjectRuntime`，并将其传递给 Agent、命令处理和新面板。Chat Area 扩展显示审批卡片、MCP 来源、Hook 事件、上下文摘要与子任务状态；Status Bar 显示预算、并发任务和待审批数。

`config.yaml` 增加版本化的 `security`、`context`、`memory`、`extensions`、`mcp`、`orchestration` 配置节。默认配置采取最保守行为：只读默认允许，所有写入、命令、外部调用和工作树创建均需审批。环境变量继续承载密钥，示例配置不得包含真实密钥。

## 模块交互

一次普通 Agent 调用的顺序：

1. TUI 将用户输入交给 ProjectRuntime。
2. Context Planner 生成可见的 ContextPlan。
3. Agent 使用该快照请求模型；模型返回本地或 MCP 工具调用。
4. Agent 将每次调用转交 Security Gateway。
5. Gateway 解析资源、执行策略；若需要审批，发出事件并暂停该调用。
6. 用户决定后，Gateway 执行或拒绝，写入 AuditEntry，结果作为工具消息回到 Agent。
7. Agent 继续循环，TUI 持续渲染事件。

Skill、命令、Hook 与子 Agent 不直接执行工具：它们创建带来源的 ExecutionRequest，走同一网关。Team Coordinator 创建 TaskSpec；Task Runner 为其创建最小权限和上下文的子运行时，必要时由 Worktree Manager 创建隔离工作树。子任务事件上报给协调器，但文件变更采纳仍需用户确认。

## 文件组织

```text
src/mewcode/
├── engine/
│   ├── security/         # 策略、审批、审计、工作区、执行网关
│   ├── context/          # 预算、规划、压缩、记忆
│   ├── extensions/       # Skill、命令、Hook 目录与运行器
│   ├── mcp/              # 服务配置、客户端、工具适配与管理
│   ├── orchestration/    # 子任务、Worktree、团队与合并审查
│   ├── agent.py          # 通过网关调用工具并使用 ContextPlan
│   ├── agent_events.py   # 审批、扩展、任务事件
│   ├── conversation.py   # 会话摘要与元数据接口
│   └── tools/            # 统一 Tool 元数据与现有工具
├── tui/
│   ├── app.py            # ProjectRuntime 组装与命令分发
│   └── widgets/          # 审批、上下文、任务状态展示
├── config.py             # 新配置读取与默认值
└── cli.py                # 可选的工作区、服务及自动化入口

specs/08-claude-code-capabilities/
├── spec.md
├── plan.md
├── task.md               # 下一阶段：带状态的实施进度文档
└── checklist.md
```

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 执行安全边界 | 集中式 Security Gateway | 避免模型、MCP、Hook 和子 Agent 出现绕过权限的平行执行路径。 |
| 权限默认值 | 只读允许，其余显式审批 | 与现有工具能力兼容，同时先解决最高风险。 |
| 工作区隔离 | 规范化路径与符号链接后验证包含关系 | 仅拼接相对路径无法阻止绝对路径或链接逃逸。 |
| 长上下文策略 | 显式 ContextPlan + 渐进压缩 | 能解释成本与信息选择，不把压缩变为不可见副作用。 |
| 记忆隔离 | 以规范化项目根目录为硬边界 | 防止项目间信息泄露。 |
| 扩展模型 | 声明式目录 + 统一执行网关 | 便于发现、审计和权限复用。 |
| MCP 接入 | 适配为标准 Tool | 保持 Agent 与模型适配层对工具来源无感。 |
| 子任务隔离 | 每个任务独立运行时和权限上限 | 遵循最小权限，支持安全并行。 |
| 变更采纳 | Worktree 结果由用户确认后采纳 | 不自动覆盖主工作区或其他 Agent 修改。 |
| 交付次序 | 先安全，再扩展与并行 | 后续能力的风险由第一阶段统一承接。 |

## 测试策略

- 为策略、路径边界、审批许可、审计、上下文选择、记忆隔离、扩展目录、MCP 适配、任务状态和 Worktree 生命周期分别建立单元测试。
- 使用伪 LLM、伪 MCP 服务与临时 Git 仓库完成集成测试，避免真实网络和真实项目文件被修改。
- 为每个拒绝路径建立测试：工作区逃逸、无权限写入、审批拒绝、Hook 失败、MCP 超时、记忆跨项目读取、子任务权限扩大和 Worktree 冲突。
- 通过 Textual 测试验证审批、上下文、MCP、Hook 和任务事件在 UI 中可见且可操作。
- 每一阶段完成时运行既有完整测试套件和新增阶段测试；兼容性测试读取旧会话数据与既有配置。

## 风险与缓解

- MCP 协议和传输方式增加依赖复杂度：以接口隔离客户端，并从最小工具调用范围开始。
- 审批等待可能阻塞 Agent Loop：用事件驱动的可取消等待，并保留会话一致性。
- 上下文压缩可能丢失关键信息：保留摘要来源、允许用户查看计划，压缩失败时降级为原始历史。
- Worktree 和并发任务可能留下临时目录：使用 Lease 记录并在启动和退出时检测、提示清理。
- Hook/Skill 可成为隐蔽执行载体：所有声明可见、默认禁用未信任来源，且始终经过网关。
