"""Chat area widget for displaying conversation"""

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
        self._stream_widget_id = "__streaming__"

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

    def add_assistant_message_start(self) -> None:
        """开始 AI 消息（流式输出前调用）"""
        self._stream_buffer = ""
        self._is_streaming = True
        header = Text()
        header.append("[...] ", style="dim")
        header.append("MewCode: ", style="bold blue")
        placeholder = Static(header, id=self._stream_widget_id, classes="chat-msg assistant-msg")
        self._get_scroll_container().mount(placeholder)
        self._scroll_to_bottom()

    def add_stream_chunk(self, chunk: str) -> None:
        """添加流式响应块，实时更新流式控件"""
        self._stream_buffer += chunk
        try:
            stream_widget = self.query_one(f"#{self._stream_widget_id}", Static)
            stream_widget.update(self._build_assistant_text("[...]", self._stream_buffer))
        except Exception:
            pass
        self._scroll_to_bottom()

    def add_assistant_message_end(self) -> None:
        """结束 AI 消息（流式输出后调用）
        移除流式期间反复 update() 的控件，替换为全新的 Static。
        新控件从未被 update() 过，文本选择可正常工作。
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

        # 移除流式控件
        try:
            stream_widget = self.query_one(f"#{self._stream_widget_id}", Static)
            stream_widget.remove()
        except Exception:
            pass

        # 全新 Static，从未被 update()，支持文本选择
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
