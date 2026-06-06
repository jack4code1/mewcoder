"""Status bar widget for displaying status information"""

from datetime import datetime

from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label


class StatusBar(Widget):
    """状态栏组件"""

    model: reactive[str] = reactive("Unknown")
    token_usage: reactive[str] = reactive("0/0")
    session_duration: reactive[str] = reactive("00:00:00")
    working_dir: reactive[str] = reactive("")
    agent_status: reactive[str] = reactive("Idle")
    mode: reactive[str] = reactive("Chat")

    def __init__(self, id: str = None):
        super().__init__(id=id)
        self.start_time = datetime.now()

    def compose(self):
        """Compose the status bar"""
        yield Label(self._format_status(), id="status-label")

    def on_mount(self) -> None:
        """Initialize on mount"""
        import os
        self.working_dir = os.getcwd()

        # Start timer to update duration
        self.set_interval(1, self._update_duration)

    def _update_duration(self) -> None:
        """Update session duration"""
        duration = datetime.now() - self.start_time
        hours, remainder = divmod(int(duration.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.session_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self._update_display()

    def _format_status(self) -> str:
        """Format status string"""
        return (
            f"[{self.model}] "
            f"[Tokens: {self.token_usage}] "
            f"[{self.session_duration}] "
            f"[{self.working_dir}] "
            f"[{self.agent_status}] "
            f"[{self.mode}]"
        )

    def _update_display(self) -> None:
        """Update the display"""
        try:
            label = self.query_one("#status-label", Label)
            label.update(self._format_status())
        except Exception:
            pass

    def update_model(self, model: str) -> None:
        """Update model name"""
        self.model = model
        self._update_display()

    def update_token_usage(self, used: int, total: int) -> None:
        """Update token usage"""
        self.token_usage = f"{used}/{total}"
        self._update_display()

    def update_agent_status(self, status: str) -> None:
        """Update agent status"""
        self.agent_status = status
        self._update_display()

    def update_mode(self, mode: str) -> None:
        """Update mode"""
        self.mode = mode
        self._update_display()
