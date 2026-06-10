# UI Fix V6.1 Plan

## Current Evidence

V6 UI 当前存在布局回归。用户截图显示：

- 聊天区只剩顶部一条边框。
- 输入区占据几乎整个主屏幕。
- Agent 输出区域不可见。

本地 `run_test()` 尺寸探测确认：

```text
size (120, 30) startup: chat=0, input=26
size (100, 20) startup: chat=0, input=16
size (80, 12)  startup: chat=0, input=8
```

这说明 `ChatArea` 不是没有消息，而是实际布局高度为 0。

当前相关 CSS：

```css
#chat-area {
    height: 1fr;
}

#input-box {
    height: auto;
    min-height: 3;
}
```

在 Textual 的 `Vertical` 布局中，`InputBox height: auto` 没有被上限约束，导致它吞掉主布局剩余高度，把 `ChatArea` 挤压成 0。

## Scope

V6.1 只修 UI 布局回归，不重构 Agent Loop、不改工具层、不改 Prompt。

本次重点：

1. 修复 ChatArea 被压成 0 高度。
2. 限制 InputBox 占位。
3. 保持 StatusBar 在输入框上方，但不能破坏主布局。
4. 增加能捕获该回归的布局测试。
5. 保留 V6 已完成的输入内容显示/隐藏状态栏行为，除非它直接导致布局问题。

## Architecture

当前主布局保持不变：

```python
Vertical(
    ChatArea(id="chat-area"),
    StatusBar(id="status-bar"),
    InputBox(id="input-box"),
    id="main-layout",
)
```

修复方式集中在布局约束：

```text
main-layout: height = 1fr
chat-area:   height = 1fr, min-height >= 3
status-bar:  height = 1, hidden 时 display none
input-box:   fixed/ bounded height, 不参与抢占剩余空间
```

目标尺寸关系：

```text
Screen
├── Header
├── main-layout (1fr)
│   ├── ChatArea   (1fr, consumes remaining space)
│   ├── StatusBar  (0 or 1 row)
│   └── InputBox   (fixed 3 rows, max 3 or 4)
└── Footer
```

## CSS Strategy

### ChatArea

给 `#chat-area` 增加最低高度，避免极小窗口下完全消失：

```css
#chat-area {
    height: 1fr;
    min-height: 3;
}
```

### InputBox

把输入区从 `height: auto` 改成受控高度：

```css
#input-box {
    height: 3;
    min-height: 3;
    max-height: 3;
}
```

如果 Textual 对 `max-height` 支持不稳定，则使用：

```css
#input-box {
    height: 3;
    min-height: 3;
}
```

并通过内部子组件高度约束保证它不扩张。

### Input 内部行

给 InputBox 内部横向容器一个稳定 id，例如：

```python
Horizontal(
    Label(">>> ", id="prompt"),
    Input(..., id="input-field"),
    id="input-row",
)
```

对应 CSS：

```css
#input-row {
    height: 1;
}

#input-field {
    height: 1;
}
```

`InputBox` 的 3 行高度用于：上边框、输入行、下边框。

### StatusBar

保留 V6 行为：

```css
#status-bar {
    height: 1;
    min-height: 1;
}

#status-bar.hidden {
    display: none;
}
```

状态栏显示时最多占 1 行，隐藏时不占布局空间。

## Functional Behavior

### Startup

- ChatArea 可见。
- 欢迎消息可见。
- StatusBar 隐藏。
- InputBox 高度固定为 3 行左右。

### Typing

- 输入内容非空时 StatusBar 显示。
- ChatArea 高度减少最多 1 行。
- InputBox 高度不变。

### Submit

- 输入框清空。
- StatusBar 隐藏。
- 用户消息显示在 ChatArea。
- Agent 输出显示在 ChatArea。

### Streaming

- `add_assistant_message_start()` 创建 streaming widget 后，ChatArea 高度仍大于 0。
- `add_stream_chunk()` 更新内容后，文本可见。
- `add_assistant_message_end()` 后最终 assistant 消息保留在 ChatArea。

## Test Plan

### 更新 `tests/test_tui_ui_layout.py`

新增/修改测试：

1. `test_chat_area_visible_at_startup_desktop`
   - size `(120, 30)`
   - assert `chat_area.size.height > 0`
   - assert `input_box.size.height <= 4`
   - assert `chat_area.size.height > input_box.size.height`

2. `test_chat_area_visible_at_startup_medium`
   - size `(100, 20)`
   - assert `chat_area.size.height > 0`
   - assert welcome message widget exists

3. `test_chat_area_visible_at_startup_small`
   - size `(80, 12)`
   - assert `chat_area.size.height > 0`
   - assert `input_box.size.height >= 3`
   - assert `input_box.size.height <= 4`

4. `test_typing_status_bar_does_not_collapse_chat`
   - type text
   - assert `status_bar.is_visible is True`
   - assert `chat_area.size.height > 0`
   - assert `input_box.size.height <= 4`

5. `test_streaming_output_visible_in_chat_area`
   - call `chat_area.add_assistant_message_start()`
   - call `chat_area.add_stream_chunk("hello")`
   - assert streaming widget exists
   - assert `chat_area.size.height > 0`

6. `test_submit_keeps_chat_area_visible`
   - submit fake user input
   - assert input clears
   - assert user message exists in ChatArea
   - assert `chat_area.size.height > 0`

### Existing Tests

Continue running:

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/test_input_box.py tests/test_status_bar_metrics.py tests/test_tui_ui_layout.py -p no:cacheprovider --basetemp=E:\agent_class\project\.bt -v
```

Then full suite:

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests -p no:cacheprovider --basetemp=E:\agent_class\project\.bt -v
```

## Risks

1. Textual CSS `max-height` may not behave like browser CSS.
   - Mitigation: rely primarily on fixed `height: 3`.

2. Very small terminal windows may not fit Header + ChatArea + InputBox + Footer.
   - Mitigation: define minimum supported height in tests, likely `80x12`.

3. StatusBar visibility updates may still be correct while layout is wrong.
   - Mitigation: tests must assert rendered widget heights, not only CSS classes.

4. Existing tests passed despite broken UI.
   - Mitigation: V6.1 tests must assert positive ChatArea height and bounded InputBox height.
