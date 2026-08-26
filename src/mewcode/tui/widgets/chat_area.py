"""Chat area widget for displaying conversation"""

import uuid
from datetime import datetime

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from textual.containers import ScrollableContainer
from textual.widget import Widget
from textual.widgets import Static

# 用于将 Rich renderable 转为 Text 对象的控制台（不可见，仅捕获）
_capture_console = Console(width=80, force_terminal=True, no_color=False)


def _render_to_text(renderable) -> Text:
    """将 Rich renderable 渲染为 Text 对象，使 Static 支持文本选择"""
    with _capture_console.capture() as capture:
        _capture_console.print(renderable)
    return Text.from_ansi(capture.get())


class ChatArea(Widget):
    """聊天区域组件，支持文本选择和复制"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._stream_buffer = ""
        self._is_streaming = False
        self._messages = []  # 存储所有消息
        # 流式占位 widget 的 ID 每次都重新生成,避免本章「第一次 stream
        # → 工具 → 第二次 stream」时,上一轮的 remove() 还没异步完成,
        # 新一轮 mount 撞同 ID 报「widget already exists」。
        self._stream_widget_id: str | None = None

    def compose(self):
        """Compose the chat area"""
        yield ScrollableContainer(id="chat-scroll")

    def _get_scroll_container(self) -> ScrollableContainer:
        return self.query_one("#chat-scroll", ScrollableContainer)

    def _build_assistant_text(self, timestamp: str, content: str) -> Text:
        """构建 AI 消息的 Text 对象（header + markdown 渲染结果）"""
        header = Text()
        header.append(f"[{timestamp}] ", style="dim")
        header.append("MewCode: ", style="bold blue")
        header.append("\n")
        md_text = _render_to_text(Markdown(content))
        header.append(md_text)
        return header

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._messages.append({"role": "user", "content": content, "timestamp": timestamp})
        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append("You: ", style="bold green")
        text.append(content)
        widget = Static(text, classes="chat-msg user-msg")
        self._get_scroll_container().mount(widget)
        self._scroll_to_bottom()

    def add_approval_request(
        self, request_id: str, tool_name: str, summary: str,
        approval: dict | None = None,
    ) -> None:
        """Render a structured, selectable approval prompt in the chat transcript."""
        approval = approval or {}
        text = Text()
        text.append("Approval required\n", style="bold yellow")
        text.append(f"Tool: {tool_name}\n")
        text.append(f"Target: {approval.get('resource_summary') or summary}\n")
        text.append(f"Operation: {approval.get('operation', 'unknown')}\n")
        text.append(f"Risk: {approval.get('risk', 'unknown')}\n", style="yellow")
        text.append("Choose an action in the approval dialog.", style="cyan")
        self._get_scroll_container().mount(Static(text, classes="chat-msg system-msg"))
        self._scroll_to_bottom()

    def add_assistant_message_start(self) -> None:
        """开始 AI 消息(流式输出前调用)"""
        self._stream_buffer = ""
        self._is_streaming = True
        # 每次开新流都用全新的 ID
        self._stream_widget_id = f"streaming-{uuid.uuid4().hex[:12]}"
        header = Text()
        header.append("[...] ", style="dim")
        header.append("MewCode: ", style="bold blue")
        placeholder = Static(header, id=self._stream_widget_id, classes="chat-msg assistant-msg")
        self._get_scroll_container().mount(placeholder)
        self._scroll_to_bottom()

    def add_stream_chunk(self, chunk: str) -> None:
        """添加流式响应块,实时更新流式控件"""
        self._stream_buffer += chunk
        if not self._stream_widget_id:
            return
        try:
            stream_widget = self.query_one(f"#{self._stream_widget_id}", Static)
            stream_widget.update(self._build_assistant_text("[...]", self._stream_buffer))
        except Exception:
            pass
        self._scroll_to_bottom()

    def add_assistant_message_end(self) -> None:
        """结束 AI 消息(流式输出后调用)
        移除流式期间反复 update() 的控件,替换为全新的 Static。
        新控件从未被 update() 过,文本选择可正常工作。
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        content = self._stream_buffer
        self._messages.append({
            "role": "assistant",
            "content": content,
            "timestamp": timestamp,
        })
        self._is_streaming = False
        self._stream_buffer = ""

        # 移除流式控件(remove 是异步的;ID 即将被丢弃,新一轮会用新 ID,
        # 不会发生 ID 冲突)
        old_id = self._stream_widget_id
        self._stream_widget_id = None
        if old_id:
            try:
                stream_widget = self.query_one(f"#{old_id}", Static)
                stream_widget.remove()
            except Exception:
                pass

        # 全新 Static,从未被 update(),支持文本选择
        text = self._build_assistant_text(timestamp, content)
        new_widget = Static(text, classes="chat-msg assistant-msg")
        self._get_scroll_container().mount(new_widget)
        self._scroll_to_bottom()

    def add_assistant_message(self, content: str) -> None:
        """添加完整 AI 消息（非流式）"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._messages.append({"role": "assistant", "content": content, "timestamp": timestamp})
        text = self._build_assistant_text(timestamp, content)
        widget = Static(text, classes="chat-msg assistant-msg")
        self._get_scroll_container().mount(widget)
        self._scroll_to_bottom()

    def add_system_message(self, content: str) -> None:
        """添加系统消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._messages.append({"role": "system", "content": content, "timestamp": timestamp})
        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append("System: ", style="bold yellow")
        text.append(content)
        widget = Static(text, classes="chat-msg system-msg")
        self._get_scroll_container().mount(widget)
        self._scroll_to_bottom()

    # ------------------------------------------------------------------
    # Tool-call trace (chapter 02-tools)
    # ------------------------------------------------------------------

    def add_tool_call(self, tool_name: str, params_summary: str) -> str:
        """添加一行工具调用占位:`→ tool_name(summary)`,返回 widget id 用于 update。"""
        widget_id = f"tool-{uuid.uuid4().hex[:12]}"
        text = Text()
        text.append("→ ", style="bold cyan")
        text.append(f"{tool_name}", style="bold cyan")
        text.append(f"({params_summary})", style="dim cyan")
        widget = Static(text, id=widget_id, classes="chat-msg tool-msg")
        # 把 tool_name + params 存在控件实例上,update 时复用
        widget._mew_tool_name = tool_name  # type: ignore[attr-defined]
        widget._mew_tool_params = params_summary  # type: ignore[attr-defined]
        self._get_scroll_container().mount(widget)
        self._scroll_to_bottom()
        return widget_id

    def update_tool_call_result(
        self, widget_id: str, success: bool, summary: str
    ) -> None:
        """把对应的 tool 行更新为 ✓ / ✗ 形态。"""
        try:
            w = self.query_one(f"#{widget_id}", Static)
        except Exception:
            return
        tool_name = getattr(w, "_mew_tool_name", "tool")
        params = getattr(w, "_mew_tool_params", "")

        text = Text()
        if success:
            text.append("✓ ", style="bold green")
            text.append(f"{tool_name}", style="bold green")
            text.append(f"({params})", style="dim green")
            if summary:
                text.append(f": {summary}", style="dim")
        else:
            text.append("✗ ", style="bold red")
            text.append(f"{tool_name}", style="bold red")
            text.append(f"({params})", style="dim red")
            if summary:
                text.append(f": {summary}", style="red")
        try:
            w.update(text)
        except Exception:
            pass
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        """滚动到底部"""
        try:
            container = self._get_scroll_container()
            container.scroll_end(animate=False)
        except Exception:
            pass

    def clear(self) -> None:
        """清空聊天区域"""
        container = self._get_scroll_container()
        container.remove_children()
        self._messages = []
        self._stream_buffer = ""
        self._is_streaming = False
        self._stream_widget_id = None
