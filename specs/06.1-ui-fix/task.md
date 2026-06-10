# UI Fix V6.1 Tasks

## Task 1: 增加布局回归测试，先复现 ChatArea 高度为 0

### 目标

补上 V6 测试盲区：之前只验证 InputBox 至少一行，没有验证 ChatArea 必须可见、InputBox 必须有最大占位限制。

### 文件影响

修改：

- `tests/test_tui_ui_layout.py`

### 步骤

1. 新增 `test_chat_area_visible_at_startup_desktop`：
   - `run_test(size=(120, 30))`
   - 断言 `chat_area.size.height > 0`
   - 断言 `input_box.size.height <= 4`
   - 断言 `chat_area.size.height > input_box.size.height`

2. 新增 `test_chat_area_visible_at_startup_medium`：
   - `run_test(size=(100, 20))`
   - 断言 `chat_area.size.height > 0`

3. 新增 `test_chat_area_visible_at_startup_small`：
   - `run_test(size=(80, 12))`
   - 断言 `chat_area.size.height > 0`
   - 断言 `3 <= input_box.size.height <= 4`

4. 新增 `test_typing_status_bar_does_not_collapse_chat`：
   - 输入非空内容触发 StatusBar 显示
   - 断言 `status_bar.is_visible is True`
   - 断言 `chat_area.size.height > 0`
   - 断言 `input_box.size.height <= 4`

### 验证

在修复前，这些测试应能暴露当前问题：

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/test_tui_ui_layout.py -p no:cacheprovider --basetemp=E:\agent_class\project\.bt -v
```

---

## Task 2: 收紧 app.py 主布局 CSS

### 目标

让 ChatArea 获取剩余空间，让 InputBox 不再吞掉主布局。

### 文件影响

修改：

- `src/mewcode/tui/app.py`

### 步骤

1. 修改 `#chat-area`：
   - 保留 `height: 1fr`
   - 增加 `min-height: 3`

2. 修改 `#input-box`：
   - 将 `height: auto` 改为固定高度，例如 `height: 3`
   - 保留 `min-height: 3`
   - 如 Textual 支持，增加 `max-height: 3`
   - 保留边框、margin、padding

3. 保持 `#status-bar.hidden { display: none; }`

4. 确认 `#main-layout` 仍是 `height: 1fr`

### 验证

运行布局探测或测试，确认：

```text
120x30: chat-area > 0, input-box <= 4
100x20: chat-area > 0, input-box <= 4
80x12:  chat-area > 0, input-box <= 4
```

---

## Task 3: 给 InputBox 内部行增加稳定高度约束

### 目标

防止 InputBox 外层固定后，内部 `Horizontal` / `Input` 自己扩张或撑破边框。

### 文件影响

修改：

- `src/mewcode/tui/widgets/input_box.py`
- `src/mewcode/tui/app.py`

### 步骤

1. 在 `InputBox.compose()` 中给内部 `Horizontal` 增加 id：

```python
Horizontal(
    Label(">>> ", id="prompt"),
    Input(placeholder="Type your message...", id="input-field"),
    id="input-row",
)
```

2. 在 app CSS 中增加：

```css
#input-row {
    height: 1;
}

#input-field {
    height: 1;
}
```

3. 保持 `#prompt` 宽度为 4，不改变输入事件逻辑。

### 验证

- 输入框只显示一行输入。
- 输入框边框完整。
- 输入框不吞掉 ChatArea 高度。

---

## Task 4: 验证消息输出真的能显示

### 目标

确认修复后不只是区域高度正确，消息 widget 也能显示在 ChatArea 中。

### 文件影响

修改：

- `tests/test_tui_ui_layout.py`

### 步骤

1. 新增 `test_chat_area_displays_system_message_at_startup`：
   - 启动 app
   - 查找 `#chat-scroll` 下的子节点
   - 断言至少存在欢迎消息 widget
   - 断言 `chat_area.size.height > 0`

2. 新增 `test_streaming_output_visible_in_chat_area`：
   - 调用 `chat_area.add_assistant_message_start()`
   - 调用 `chat_area.add_stream_chunk("hello")`
   - 断言 streaming widget 存在
   - 断言 `chat_area.size.height > 0`

3. 新增 `test_submit_keeps_chat_area_visible` 或扩展现有提交测试：
   - 输入并提交用户消息
   - 断言 ChatArea 中新增用户消息 widget
   - 断言 `chat_area.size.height > 0`

### 验证

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/test_tui_ui_layout.py -p no:cacheprovider --basetemp=E:\agent_class\project\.bt -v
```

---

## Task 5: 保持 V6 已有行为不回归

### 目标

修复布局时不能破坏 V6 已完成的状态栏显隐、输入清空、指标更新行为。

### 文件影响

无新增，运行现有测试验证。

### 步骤

运行：

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/test_input_box.py tests/test_status_bar_metrics.py tests/test_tui_ui_layout.py -p no:cacheprovider --basetemp=E:\agent_class\project\.bt -v
```

### 验证

以下行为仍通过：

- 输入内容非空时 StatusBar 显示。
- 清空输入时 StatusBar 隐藏。
- 提交后输入框清空。
- 隐藏期间 status metrics 仍更新。
- InputBox 至少一行可输入。

---

## Task 6: 跑 TUI / Agent Loop 回归测试

### 目标

确认 UI 布局修复不影响 Agent Loop 事件消费、工具 trace、metrics 更新。

### 文件影响

无新增，运行现有测试验证。

### 步骤

运行：

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/test_tui_agent_loop.py tests/test_tui_tool_flow.py tests/test_tui_metrics.py tests/test_tui_tool_trace.py -p no:cacheprovider --basetemp=E:\agent_class\project\.bt -v
```

### 验证

全部通过。

---

## Task 7: 跑完整测试套件

### 目标

确认 V6.1 没有引入全局回归。

### 文件影响

无新增，运行全量测试。

### 步骤

运行：

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests -p no:cacheprovider --basetemp=E:\agent_class\project\.bt -v
```

### 验证

全部通过，或记录明确失败用例和原因。

---

## Task 8: 更新文档与 CHANGELOG

### 目标

记录 V6.1 修复范围和验证证据。

### 文件影响

修改：

- `README.md`（如已有 UI 布局说明需要同步）
- `MANUAL.md`（如已有 UI 布局说明需要同步）
- `CHANGELOG.md`

### 步骤

1. 在 CHANGELOG 中增加 V6.1 条目：
   - 修复 ChatArea 被 InputBox 挤压为 0 高度。
   - 限制 InputBox 高度。
   - 增加 ChatArea 可见性和输出可见性测试。

2. 如果 README / MANUAL 已描述 V6 UI：
   - 补充输入区为紧凑单行输入区。
   - 补充状态栏显示时不应遮挡聊天区。

### 验证

- 文档描述与实际 UI 一致。
- CHANGELOG 能让后续 agent 理解本次是 V6 回归修复。
