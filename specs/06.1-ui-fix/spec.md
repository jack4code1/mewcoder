# UI Fix V6.1 Spec

## 背景

V6 UI 重构后，应用页面出现严重布局回归：

1. Agent 输出区域不可见。
2. 输入区占用过大，几乎吞掉整个主布局。
3. 用户看到的界面中，聊天区只剩顶部一条边框，输入框占据大部分屏幕。

经过本地验证，这不是 Agent Loop 或模型输出链路优先问题，而是布局问题：

```text
120x30 startup: chat-area height = 0, input-box height = 26
100x20 startup: chat-area height = 0, input-box height = 16
80x12  startup: chat-area height = 0, input-box height = 8
```

当前 `#input-box { height: auto; min-height: 3; }` 会让输入区在主 `Vertical` 布局中吞掉剩余空间，导致 `#chat-area { height: 1fr; }` 实际渲染高度为 0。

## 目标

V6.1 是 V6 UI 的回归修复版本，不做新的大设计，只恢复可用性并补齐测试盲区。

目标：

1. ChatArea 必须始终可见。
2. Agent 输出、用户消息、系统消息、工具调用 trace 必须能显示在聊天区。
3. InputBox 必须保持紧凑，不能吞掉主布局空间。
4. StatusBar 可以继续位于输入框上方，但不能挤压 ChatArea 到不可用。
5. 小窗口下仍要保证：
   - ChatArea 至少有可见高度。
   - InputBox 至少完整显示一行输入。
   - Footer 不遮挡输入区。
6. 测试必须能捕获“ChatArea 被压成 0 高度”的回归。

## 用户可见行为

启动后：

- 顶部显示聊天区，并能看到欢迎消息。
- 底部显示紧凑输入区。
- 输入区高度固定或受控，不应随窗口高度扩张。
- 状态栏默认隐藏或折叠，但不影响聊天区可见性。

输入时：

- 状态栏可以显示在输入框上方。
- ChatArea 可以略微变小，但高度不能变成 0。
- 输入框仍保持紧凑。

提交消息后：

- 用户消息立即显示在 ChatArea。
- Agent 流式输出显示在 ChatArea。
- 工具调用 trace 显示在 ChatArea。
- 输入框清空并保持紧凑。

## 非目标

本次不做：

1. Prompt 系统调整。
2. Agent Loop 重构。
3. Tool 执行逻辑修改。
4. 新增多行编辑器。
5. 复杂响应式 UI 主题重做。
6. 状态栏信息结构大改。

## 验收重点

V6.1 的验收不只看测试通过，还必须验证布局尺寸：

1. 在 `120x30` 终端下：
   - ChatArea 高度大于 0，且明显大于 InputBox。
   - InputBox 不超过 3 或 4 行。

2. 在 `100x20` 终端下：
   - ChatArea 高度大于 0。
   - 欢迎消息可见。
   - 输入框紧凑。

3. 在 `80x12` 小窗口下：
   - ChatArea 仍有可见高度。
   - InputBox 至少一行可输入。
   - Footer 不覆盖输入框。

4. 提交一条 fake assistant 流式消息时：
   - ChatArea 中能看到 assistant 输出。
   - 输出不会被输入区遮挡。

5. 回归测试必须包含：
   - `chat_area.size.height > 0`
   - `input_box.size.height <= 4`
   - `chat_area.size.height > input_box.size.height`
