"""Input box widget for user input"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Label


class InputBox(Widget):
    """输入框组件"""

    BINDINGS = [
        Binding("enter", "submit", "Submit"),
        Binding("up", "history_prev", "Previous"),
        Binding("down", "history_next", "Next"),
        Binding("tab", "tab_complete", "Complete"),
    ]

    history: reactive[list[str]] = reactive(list)
    history_index: reactive[int] = reactive(-1)

    def compose(self) -> ComposeResult:
        """Compose the input box"""
        yield Horizontal(
            Label(">>> ", id="prompt"),
            Input(placeholder="Type your message...", id="input-field"),
        )

    def on_mount(self) -> None:
        """Initialize on mount"""
        self.history = []
        self.history_index = -1

    def action_submit(self) -> None:
        """Submit the input"""
        input_field = self.query_one("#input-field", Input)
        value = input_field.value.strip()

        if value:
            # Add to history
            self.history.append(value)
            self.history_index = len(self.history)

            # Clear input
            input_field.value = ""

            # Post message to parent
            self.post_message(InputSubmitted(value))

    def action_history_prev(self) -> None:
        """Navigate to previous history item"""
        if self.history and self.history_index > 0:
            self.history_index -= 1
            input_field = self.query_one("#input-field", Input)
            input_field.value = self.history[self.history_index]

    def action_history_next(self) -> None:
        """Navigate to next history item"""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            input_field = self.query_one("#input-field", Input)
            input_field.value = self.history[self.history_index]
        elif self.history_index == len(self.history) - 1:
            self.history_index = len(self.history)
            input_field = self.query_one("#input-field", Input)
            input_field.value = ""

    def action_tab_complete(self) -> None:
        """Tab completion or prompt optimization"""
        input_field = self.query_one("#input-field", Input)
        value = input_field.value

        if value.startswith("/"):
            # Command completion
            self._complete_command(value)
        else:
            # Check for double tab (prompt optimization)
            # This is a simplified version - in production, you'd want to track tab timing
            self.post_message(TabPressed(value))

    def _complete_command(self, value: str) -> None:
        """Complete command"""
        commands = ["/help", "/copy", "/clear", "/save", "/model", "/mode", "/quit"]
        matches = [cmd for cmd in commands if cmd.startswith(value)]

        if len(matches) == 1:
            input_field = self.query_one("#input-field", Input)
            input_field.value = matches[0]
        elif matches:
            # Show available commands
            self.post_message(ShowCommands(matches))


class InputSubmitted(Message):
    """Message posted when input is submitted"""

    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value


class TabPressed(Message):
    """Message posted when tab is pressed"""

    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value


class ShowCommands(Message):
    """Message to show available commands"""

    def __init__(self, commands: list[str]) -> None:
        super().__init__()
        self.commands = commands
