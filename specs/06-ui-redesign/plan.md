# UI 界面重构 Plan

## 架构概览

本次重构集中在 TUI 表现层，涉及三个改动面：

1. **布局顺序调整**（`app.py` 的 `compose` 与 CSS）：把 `StatusBar` 从 `InputBox` 下方移动到 `InputBox` 上方，使区域顺序变为 Header → ChatArea → StatusBar → InputBox → Footer。
2. **状态区条件显隐**（`StatusBar` + `app.py` 协调）：`StatusBar` 增加可见性控制；`app.py`/`InputBox` 在输入内容变化、提交、流式开始/结束等时机驱动显隐。
3. **输入区高度健壮性**（`app.py` CSS）：放宽输入框的固定高度约束，保证至少一行可见且不被裁切。

核心交互信号是「输入框当前是否为空」。该信号由 `InputBox` 在文本变化时对外广播，由 `MewCodeApp` 接收并切换 `StatusBar` 的可见性。`StatusBar` 自身只负责「显示/隐藏」与「内容更新」两件事，不感知输入框。

## 核心数据结构

### InputChanged（新增消息类）

`InputBox` 在其子 `Input` 内容发生变化时发出的消息，承载当前是否有非空内容。

- 字段：`has_content: bool` —— 当前输入框去除首尾空白后是否非空。
- 继承 `textual.message.Message`，构造时调用 `super().__init__()`。
- 用途：`MewCodeApp` 订阅该消息以决定 `StatusBar` 显隐。

### StatusBar.visible_state（新增可见性控制）

`StatusBar` 增加一个布尔反应式属性与一对方法，控制自身是否在布局中占位。

- `is_visible: reactive[bool]`（默认 `False`，启动时输入框为空 → 隐藏）。
- `show()` —— 设为可见。
- `hide()` —— 设为隐藏。
- 显隐通过切换 CSS 类（如 `hidden`）实现，隐藏时高度折叠为 0，不占布局空间。
- 隐藏期间内容更新方法（`update_token_usage` 等）照常写入反应式属性，仅渲染不可见，再次显示时反映最新值。

## 模块设计

### InputBox（`tui/widgets/input_box.py`）

**职责：** 采集用户输入；在内容变化时广播 `InputChanged`；维持既有提交/历史/补全行为。

**改动：**
- 监听子 `Input` 的 `Input.Changed` 事件，计算 `value.strip()` 是否非空，发出 `InputChanged(has_content=...)`。
- `action_submit` 清空输入后，由 `Input.Changed` 自然触发一次 `has_content=False`（或显式再发一次），确保提交后状态区隐藏。
- 既有 `action_submit` / `action_history_prev` / `action_history_next` / `action_tab_complete` / 补全逻辑保持不变。

**对外接口：** 发出 `InputSubmitted`、`TabPressed`、`ShowCommands`（既有）+ `InputChanged`（新增）。

**依赖：** 无新增外部依赖。

### StatusBar（`tui/widgets/status_bar.py`）

**职责：** 渲染状态信息（既有）+ 控制自身可见性（新增）。

**改动：**
- 新增 `is_visible: reactive[bool]`，默认 `False`。
- 新增 `show()` / `hide()` 方法，切换 `hidden` CSS 类。
- 既有 `update_model` / `update_token_usage` / `update_metrics` / `update_agent_status` / `update_mode` / 宽度自适应格式逻辑全部保留，不受可见性影响。

**对外接口：** 既有 update 系列方法 + `show()` / `hide()`。

**依赖：** 既有指标模型，无新增。

### MewCodeApp（`tui/app.py`）

**职责：** 组合布局；协调 `InputBox` 信号与 `StatusBar` 显隐。

**改动：**
- `compose`：将 `StatusBar` 放到 `InputBox` 之前（上方）。
- CSS：
  - 调整 `#status-bar` 与 `#input-box` 的顺序相关样式；为 `#status-bar` 增加 `.hidden`（或 `display: none` 等价）规则使其隐藏时不占高度。
  - 放宽 `#input-box` 高度约束：保证 `min-height` 足以容纳边框 + 至少一行输入；去除或放宽 `max-height` 导致的裁切风险。
- 新增 `on_input_changed(event: InputChanged)`：`event.has_content` 为真则 `status_bar.show()`，否则 `status_bar.hide()`。
- `on_mount`：初始化时输入框为空 → `status_bar.hide()`。
- 既有 `on_input_submitted` / `_process_with_llm` 等逻辑不变；提交清空输入框后由 `InputChanged` 驱动隐藏，无需在流程里额外处理（流式期间输入框为空 → 状态区本就隐藏，满足 F6）。

**对外接口：** 既有 actions 不变。

**依赖：** `InputBox`、`StatusBar`、`ChatArea`（既有）。

## 模块交互

显隐主流程（输入驱动）：

```
用户在 Input 打字
  → InputBox 收到 Input.Changed
  → InputBox 发出 InputChanged(has_content=True)
  → MewCodeApp.on_input_changed → StatusBar.show()
  → 状态区出现在输入框上方，对话区高度收缩

用户清空 / 提交
  → Input 内容变空（提交时 action_submit 清空）
  → InputBox 发出 InputChanged(has_content=False)
  → MewCodeApp.on_input_changed → StatusBar.hide()
  → 状态区折叠为 0 高度，对话区高度回收
```

内容更新流程（与显隐解耦）：

```
Agent Loop 事件（USAGE / METRICS / 状态变化）
  → MewCodeApp 调用 status_bar.update_*（既有）
  → StatusBar 更新反应式属性并尝试渲染
  → 若当前隐藏，仅数据更新，不可见；再次 show() 时显示最新值
```

布局顺序（compose 产出，自上而下）：

```
Header
Vertical(id=main-layout):
    ChatArea     (height: 1fr)
    StatusBar    (height: auto / 0 when hidden)   ← 移到输入框上方
    InputBox     (min-height 保证至少一行 + 边框)
Footer
```

## 文件组织

```
project/
├── src/mewcode/tui/
│   ├── app.py                    — 调整 compose 顺序、CSS、新增 on_input_changed、on_mount 初始隐藏
│   └── widgets/
│       ├── input_box.py          — 新增 InputChanged 消息、监听 Input.Changed
│       └── status_bar.py         — 新增 is_visible / show() / hide()
└── tests/
    ├── test_input_box.py         — 扩展：内容变化广播 InputChanged
    ├── test_status_bar_metrics.py— 扩展：隐藏时内容仍更新
    └── test_tui_ui_layout.py     — 新增：布局顺序、显隐切换、输入框至少一行
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 状态区显隐实现 | 切换 CSS 类使其折叠为 0 高度（`display: none` 等价），而非仅 `visible: hidden` | F7 要求隐藏时不占布局空间，由对话区回收；仅隐藏可见性会留下空行造成空白占位 |
| 显隐触发信号来源 | `InputBox` 监听 `Input.Changed` 广播 `has_content` | 显隐条件由 spec 定为「输入框是否有内容」，该信号最贴近、最及时，且让 StatusBar 与输入解耦 |
| 提交后隐藏的实现 | 复用 `action_submit` 清空输入 → `Input.Changed` 自然触发 `has_content=False` | 避免在提交/流式流程里散落显隐逻辑，单一信号源更可靠（满足 F5/F6） |
| 流式期间显隐 | 不在 Agent Loop 事件里控制显隐，完全交给输入框是否为空 | spec 明确显隐只由输入内容驱动；流式时输入框已空 → 本就隐藏，逻辑无需重复 |
| 隐藏期间是否停更内容 | 继续更新反应式属性 | F10 要求再次显示时内容最新；停更会导致显示陈旧值 |
| 输入框高度 | 用 `min-height` 保证边框 + 至少一行，放宽/移除 `max-height` 的裁切风险 | F9 要求任何尺寸至少一行可见，固定 `max-height: 4` 在小高度终端可能裁切 |
| 状态区可见时的高度 | `height: auto`（单行内容）配合既有宽度自适应 | 与原 `height: 1` 行为一致，且显示时自然占一行 |
| 是否改动宽度格式分级 | 不改 | spec 不做事项；紧凑/中等/完整三档沿用现有阈值 |
