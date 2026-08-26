"""Keyboard-driven approval dialog for controlled tool execution."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class ApprovalDialog(ModalScreen[str]):
    """Let the user resolve an approval request without typing a command."""

    BINDINGS = [
        Binding("left,up", "previous", "Previous", show=False),
        Binding("right,down", "next", "Next", show=False),
        Binding("enter", "confirm", "Confirm", show=False),
        Binding("escape", "deny", "Deny", show=False),
    ]

    CSS = """
    ApprovalDialog {
        align: center middle;
    }

    #approval-dialog {
        width: 68;
        height: auto;
        max-height: 18;
        border: heavy $warning;
        background: $surface;
        padding: 1 2;
    }

    #approval-title {
        color: $warning;
        text-style: bold;
        margin-bottom: 1;
    }

    #approval-options {
        margin-top: 1;
    }
    """

    _choices = (
        ("deny", "Deny"),
        ("once", "Allow once"),
        ("project", "Allow for this project"),
    )

    def __init__(self, tool_name: str, summary: str, approval: dict | None = None) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.summary = summary
        self.approval = approval or {}
        self.selected = 0

    def compose(self) -> ComposeResult:
        target = self.approval.get("resource_summary") or self.summary
        yield Vertical(
            Static("Approval required", id="approval-title"),
            Static(
                f"Tool: {self.tool_name}\n"
                f"Target: {target}\n"
                f"Operation: {self.approval.get('operation', 'unknown')}\n"
                f"Risk: {self.approval.get('risk', 'unknown')}",
                id="approval-details",
            ),
            Static(id="approval-options"),
            Static("Arrow keys to choose. Enter to confirm. Esc denies.", id="approval-help"),
            id="approval-dialog",
        )

    def on_mount(self) -> None:
        self._render_choices()

    def _render_choices(self) -> None:
        options = []
        for index, (_, label) in enumerate(self._choices):
            marker = ">" if index == self.selected else " "
            options.append(f"{marker} {label}")
        self.query_one("#approval-options", Static).update("\n".join(options))

    def action_previous(self) -> None:
        self.selected = (self.selected - 1) % len(self._choices)
        self._render_choices()

    def action_next(self) -> None:
        self.selected = (self.selected + 1) % len(self._choices)
        self._render_choices()

    def action_confirm(self) -> None:
        self.dismiss(self._choices[self.selected][0])

    def action_deny(self) -> None:
        self.dismiss("deny")
