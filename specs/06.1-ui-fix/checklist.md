# UI Fix V6.1 Checklist

## 文档审批

- [ ] 用户已确认 `spec.md`。
- [ ] 用户已确认 `plan.md`。
- [ ] 用户已确认 `task.md`。
- [ ] 用户已确认 `checklist.md`。
- [ ] 四份文档确认前，不修改实现代码。

## 问题复现与证据

- [ ] 已记录用户截图中的现象：
  - 聊天区不可见或只剩边框。
  - 输入区占用过大。
  - Agent 输出看起来完全不显示。
- [ ] 已通过 `run_test()` 或等价方式确认当前布局问题：
  - `chat_area.size.height == 0`
  - `input_box.size.height` 远大于 4
- [ ] 已确认优先怀疑点是布局挤压/遮挡，而不是 Agent Loop 首要故障。
- [ ] 已把上述证据写入 `spec.md` 或 `plan.md`。

## 布局尺寸验收

- [ ] 在 `120x30` 终端尺寸下：
  - `chat_area.size.height > 0`
  - `input_box.size.height <= 4`
  - `chat_area.size.height > input_box.size.height`
- [ ] 在 `100x20` 终端尺寸下：
  - `chat_area.size.height > 0`
  - `input_box.size.height <= 4`
- [ ] 在 `80x12` 终端尺寸下：
  - `chat_area.size.height > 0`
  - `input_box.size.height >= 3`
  - `input_box.size.height <= 4`
- [ ] 输入内容导致 StatusBar 显示后：
  - `status_bar.is_visible is True`
  - `chat_area.size.height > 0`
  - `input_box.size.height <= 4`
- [ ] StatusBar 隐藏时：
  - 不占布局高度。
  - ChatArea 高度不小于显示 StatusBar 时的高度。

## ChatArea 可见性验收

- [ ] 启动后 ChatArea 可见。
- [ ] 启动欢迎消息可见。
- [ ] 提交用户输入后，用户消息显示在 ChatArea。
- [ ] Agent streaming 开始后，streaming widget 显示在 ChatArea。
- [ ] Agent streaming 更新后，chunk 文本显示在 ChatArea。
- [ ] Agent streaming 结束后，最终 assistant 消息保留在 ChatArea。
- [ ] 工具调用 trace 仍显示在 ChatArea。
- [ ] 工具调用结果更新仍显示在 ChatArea。

## InputBox 验收

- [ ] InputBox 不再使用会吞掉主布局的无上限 `height: auto`。
- [ ] InputBox 高度固定或被上限约束。
- [ ] InputBox 至少完整显示一行输入。
- [ ] InputBox 不超过 4 行。
- [ ] 输入框边框完整显示。
- [ ] 输入内容不会把 InputBox 撑高。
- [ ] 提交后输入框清空。
- [ ] 空输入不会提交。
- [ ] Up / Down 历史导航仍正常。

## StatusBar 验收

- [ ] 启动时 StatusBar 默认隐藏。
- [ ] 输入内容非空时 StatusBar 显示。
- [ ] 输入清空时 StatusBar 隐藏。
- [ ] 提交后 StatusBar 隐藏。
- [ ] StatusBar 显示时最多占 1 行。
- [ ] StatusBar 隐藏时使用 `display: none` 或等价折叠方式。
- [ ] 隐藏期间调用 metrics 更新后，再次显示能看到最新状态。

## CSS / 布局结构

- [ ] `#main-layout` 保持 `height: 1fr`。
- [ ] `#chat-area` 保持 `height: 1fr`。
- [ ] `#chat-area` 有最低高度保护。
- [ ] `#input-box` 有明确固定高度或最大高度。
- [ ] `#input-row` 或等价内部容器有稳定高度。
- [ ] `#input-field` 不会撑开 InputBox。
- [ ] Footer 不遮挡输入区。
- [ ] Header / Footer 存在时，主布局仍能给 ChatArea 分配高度。

## 测试

- [ ] 新增测试能在修复前暴露 ChatArea 高度为 0 的问题。
- [ ] `tests/test_tui_ui_layout.py` 覆盖：
  - desktop 尺寸布局
  - medium 尺寸布局
  - small 尺寸布局
  - StatusBar 显示后 ChatArea 不塌陷
  - streaming 输出 widget 可见
  - 提交后 ChatArea 仍可见
- [ ] 聚焦 UI 测试通过：

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/test_input_box.py tests/test_status_bar_metrics.py tests/test_tui_ui_layout.py -p no:cacheprovider --basetemp=E:\agent_class\project\.bt -v
```

- [ ] TUI / Agent Loop 回归测试通过：

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/test_tui_agent_loop.py tests/test_tui_tool_flow.py tests/test_tui_metrics.py tests/test_tui_tool_trace.py -p no:cacheprovider --basetemp=E:\agent_class\project\.bt -v
```

- [ ] 完整测试套件通过：

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests -p no:cacheprovider --basetemp=E:\agent_class\project\.bt -v
```

## 人工验收

- [ ] 启动应用后，聊天区不是 0 高度。
- [ ] 启动应用后，欢迎消息可见。
- [ ] 输入区位于底部且只占少量高度。
- [ ] 输入一条普通消息后，用户消息可见。
- [ ] Agent 回复时，文本能在聊天区显示。
- [ ] 执行工具调用时，tool trace 能在聊天区显示。
- [ ] 缩小终端窗口后，输入区仍紧凑，聊天区仍可见。
- [ ] 页面不再出现“输入区占满屏幕、输出区看不到”的状态。

## CHANGELOG

- [ ] `CHANGELOG.md` 增加 V6.1 条目。
- [ ] 条目说明：
  - 修复 ChatArea 被 InputBox 挤压为 0 高度。
  - 限制 InputBox 高度。
  - 增加布局尺寸回归测试。
  - 增加输出可见性测试。
