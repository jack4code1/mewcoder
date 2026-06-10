"""Status bar widget for displaying status information."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label

from ...engine.models import MetricsAggregate, MetricsSnapshot, TokenUsage


class StatusBar(Widget):
    """Status bar widget."""

    model: reactive[str] = reactive("Unknown")
    token_usage: reactive[str] = reactive("N/A")
    compact_token_usage: reactive[str] = reactive("N/A")
    performance_metrics: reactive[str] = reactive("N/A")
    compact_performance_metrics: reactive[str] = reactive("N/A")
    session_duration: reactive[str] = reactive("00:00:00")
    working_dir: reactive[str] = reactive("")
    agent_status: reactive[str] = reactive("Idle")
    mode: reactive[str] = reactive("Chat")

    def __init__(self, id: str = None):
        super().__init__(id=id)
        self.start_time = datetime.now()
        self._api_metrics: Optional[MetricsAggregate] = None

    def compose(self):
        """Compose the status bar."""
        yield Label(self._format_status(), id="status-label")

    def on_mount(self) -> None:
        """Initialize on mount."""
        import os

        self.working_dir = os.getcwd()
        self.set_interval(1, self._update_duration)

    def on_resize(self, event=None) -> None:
        """Refresh width-aware status text after terminal resize."""
        self._update_display()

    def _update_duration(self) -> None:
        """Update session duration."""
        duration = datetime.now() - self.start_time
        hours, remainder = divmod(int(duration.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.session_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self._update_display()

    def _current_width(self) -> int:
        try:
            width = int(self.size.width)
        except Exception:
            width = 0
        return width if width > 0 else 120

    def _format_status(self, width: Optional[int] = None) -> str:
        """Format status string."""
        width = self._current_width() if width is None else width
        if width < 90:
            return (
                f"[{self.model}] "
                f"[Tok: {self.compact_token_usage}] "
                f"[{self.compact_performance_metrics}] "
                f"[{self.agent_status}]"
            )
        if width < 140:
            return (
                f"[{self.model}] "
                f"[Tok: {self.compact_token_usage}] "
                f"[Avg: {self.compact_performance_metrics}] "
                f"[{self.session_duration}] "
                f"[{self.agent_status}] "
                f"[{self.mode}]"
            )
        return (
            f"[{self.model}] "
            f"[Tok: {self.token_usage}] "
            f"[Avg: {self.performance_metrics}] "
            f"[{self.session_duration}] "
            f"[{self.agent_status}] "
            f"[{self.mode}] "
            f"[{self._compact_path(self.working_dir)}]"
        )

    def _update_display(self) -> None:
        """Update the display."""
        try:
            label = self.query_one("#status-label", Label)
            label.update(self._format_status())
        except Exception:
            pass

    @staticmethod
    def _compact_number(value: int) -> str:
        if abs(value) >= 1_000_000:
            text = f"{value / 1_000_000:.1f}m"
        elif abs(value) >= 1_000:
            text = f"{value / 1_000:.1f}k"
        else:
            return str(value)
        return text.replace(".0", "")

    @staticmethod
    def _compact_path(path: str) -> str:
        if not path:
            return ""
        path_obj = Path(path)
        name = path_obj.name or str(path_obj)
        parent = path_obj.parent.name
        drive = path_obj.drive
        if drive and parent:
            return f"{drive}\\...\\{parent}\\{name}"
        if parent:
            return f".../{parent}/{name}"
        return name

    @classmethod
    def _format_token_usage(cls, usage: Optional[TokenUsage]) -> tuple[str, str]:
        if usage is None:
            return "N/A", "N/A"
        total = usage.total_tokens
        if usage.prompt_tokens or usage.completion_tokens:
            wide = (
                f"{total:,} P:{usage.prompt_tokens:,} "
                f"C:{usage.completion_tokens:,}"
            )
        else:
            wide = f"{total:,}"
        return wide, cls._compact_number(total)

    @staticmethod
    def _format_ms(value: Optional[float]) -> str:
        if value is None:
            return "N/A"
        if value < 1000:
            return f"{int(round(value))}ms"
        return f"{value / 1000:.1f}s"

    @classmethod
    def _format_performance(
        cls, metrics: Optional[MetricsAggregate]
    ) -> tuple[str, str]:
        if metrics is None:
            return "N/A", "N/A"

        speed = metrics.average_output_tokens_per_second
        ttft = metrics.average_ttft_ms
        latency = metrics.average_latency_ms

        speed_text = "N/A" if speed is None else f"{speed:.1f} tok/s"
        ttft_text = cls._format_ms(ttft)
        latency_text = cls._format_ms(latency)
        wide = f"{speed_text} TTFT: {ttft_text} Lat: {latency_text}"

        if speed is not None:
            compact = speed_text
        elif ttft is not None:
            compact = f"TTFT {ttft_text}"
        elif latency is not None:
            compact = f"Lat {latency_text}"
        else:
            compact = "N/A"

        return wide, compact

    def update_model(self, model: str) -> None:
        """Update model name."""
        self.model = model
        self._update_display()

    def update_token_usage(
        self, usage: Optional[TokenUsage] | int, total: Optional[int] = None
    ) -> None:
        """Update token usage."""
        if isinstance(usage, TokenUsage) or usage is None:
            wide, compact = self._format_token_usage(usage)
        else:
            legacy_usage = TokenUsage(total_tokens=int(usage or 0))
            if total is not None and total > 0:
                legacy_usage.total_tokens = int(total)
            wide, compact = self._format_token_usage(legacy_usage)

        self.token_usage = wide
        self.compact_token_usage = compact
        self._update_display()

    def update_metrics(self, snapshot: MetricsSnapshot | MetricsAggregate) -> None:
        """Update API performance metrics."""
        if isinstance(snapshot, MetricsSnapshot):
            self._api_metrics = snapshot.api_metrics
            if snapshot.token_usage is not None:
                self.update_token_usage(snapshot.token_usage)
        else:
            self._api_metrics = snapshot

        wide, compact = self._format_performance(self._api_metrics)
        self.performance_metrics = wide
        self.compact_performance_metrics = compact
        self._update_display()

    def update_agent_status(self, status: str) -> None:
        """Update agent status."""
        self.agent_status = status
        self._update_display()

    def update_mode(self, mode: str) -> None:
        """Update mode."""
        self.mode = mode
        self._update_display()
