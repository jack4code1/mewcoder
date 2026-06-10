# UI 界面重构 Checklist

> 每一项通过运行代码或观察行为来验证，聚焦系统行为。

## 文档审批

- [ ] 用户明确批准 `specs/06-ui-redesign/spec.md`。
- [ ] 用户明确批准 `specs/06-ui-redesign/plan.md`。
- [ ] 用户明确批准 `specs/06-ui-redesign/task.md`。
- [ ] 用户明确批准 `specs/06-ui-redesign/checklist.md`。
- [ ] 四份文档全部批准前，未改动任何实现代码。

## 布局顺序（F1, F2）

- [ ] 启动应用后，`main-layout` 子组件顺序为 `ChatArea` → `StatusBar` → `InputBox`（验证：`run_test()` 查询子组件序，或肉眼观察状态区在输入框上方）。
- [ ] 状态区显示的字段与重构前一致：模型、Token、性能、时长、Agent 状态、模式、工作目录（验证：宽终端下显示一条消息后观察状态区文本，包含上述字段）。

## 状态区条件显隐（F3-F7, F10）

- [ ] 启动后输入框为空，状态区隐藏（验证：`run_test()` 断言 StatusBar 含 `hidden` 类或 `is_visible is False`）。
- [ ] 在输入框输入非空内容后，状态区可见（验证：pilot 设置 `Input.value` 为非空，断言 StatusBar 可见）。
- [ ] 清空输入框后，状态区重新隐藏（验证：pilot 清空 `Input.value`，断言 StatusBar 隐藏）。
- [ ] 提交一条消息后，输入框被清空且状态区隐藏（验证：pilot 输入并提交，断言输入框空且 StatusBar 隐藏）。
- [ ] 流式刷新期间输入框为空时，状态区保持隐藏（验证：触发处理流程中断言 StatusBar 仍隐藏）。
- [ ] 状态区隐藏时其高度不占布局空间，对话区可用高度增加（验证：对比 StatusBar 隐藏/显示两态下 ChatArea 的渲染高度，隐藏时更高）。
- [ ] 状态区隐藏期间调用 `update_token_usage`(非零) 后再 `show()`，显示最新值（验证：`tests/test_status_bar_metrics.py` 新增用例通过）。

## 无遮挡与输入框至少一行（F8, F9）

- [ ] 状态区显隐切换前后，输入框始终完整可见，无区域被裁切或重叠（验证：切换显隐两态下断言 InputBox 仍可查询且高度 ≥ 边框+1 行）。
- [ ] 最小受支持高度终端下，输入框至少完整显示一行（验证：`run_test(size=(80, 小高度))` 断言 InputBox 渲染高度容纳至少一行 + 边框）。
- [ ] `#input-box` 不再有导致裁切的 `max-height: 4` 约束（验证：检查 `app.py` CSS，`max-height: 4` 已移除或放宽）。

## 窄终端紧凑格式（N6）

- [ ] 窄宽度下状态区使用紧凑格式，文本不溢出（验证：`run_test(size=(70, h))` 显示状态区，断言文本采用紧凑分支且长度不超出宽度）。

## 既有行为不回归（N1-N3, N5）

- [ ] 既有快捷键行为不变（验证：`tests/test_tui_*` 相关用例通过）。
- [ ] 既有内置命令 `/help` `/copy` `/clear` `/save` `/model` `/mode` `/quit` 行为不变（验证：相关命令测试或手动触发观察）。
- [ ] 引擎层 / Agent Loop / 工具层无改动（验证：`git diff --stat` 仅涉及 `tui/` 与 `tests/` 与文档）。

## 测试

- [ ] `python -m pytest tests/test_input_box.py -v -p no:cacheprovider` 通过。
- [ ] `python -m pytest tests/test_status_bar_metrics.py -v -p no:cacheprovider` 通过。
- [ ] `python -m pytest tests/test_tui_ui_layout.py -v -p no:cacheprovider` 通过。
- [ ] `python -m pytest tests/test_tui_agent_loop.py tests/test_tui_tool_flow.py tests/test_tui_metrics.py -v -p no:cacheprovider` 通过。
- [ ] `python -m pytest tests -p no:cacheprovider`（ASCII basetemp）通过，或每个失败都记录了确切失败用例名与原因。

## 端到端场景

- [ ] 场景 1（输入显隐）：启动 → 状态区隐藏 → 打字 → 状态区出现在输入框上方 → 清空 → 状态区消失，全程输入框始终至少一行可见。
- [ ] 场景 2（提交流式）：输入消息并提交 → 输入框清空、状态区隐藏 → 流式回复刷新期间状态区保持隐藏 → 回复结束后再次打字 → 状态区重新出现且内容为最新 token/状态。
- [ ] 场景 3（窄终端）：缩小终端宽度与高度 → 输入框仍完整显示一行，状态区显示时用紧凑格式且不遮挡其他区域。
