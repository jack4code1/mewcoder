"""Loss-aware history compression helpers."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.message import Message, MessageRole
from .session_state import build_session_state


@dataclass(frozen=True)
class CompressionResult:
    summary: Message
    source_count: int
    degraded: bool = False


def compress_messages(messages: list[Message], keep_recent: int = 8) -> CompressionResult | None:
    """Create a schema-based historical summary; original messages remain stored."""
    old = messages[:-keep_recent] if len(messages) > keep_recent else []
    if not old:
        return None
    state = build_session_state(old)
    goals = [message.content[:240] for message in old if message.role is MessageRole.USER and message.content]
    text = "\n".join([
        f"Historical summary schema v1 ({len(old)} messages):",
        "User goals: " + (" | ".join(goals[-3:]) if goals else "none recorded"),
        "Key decisions: " + (" | ".join(state.key_decisions) if state.key_decisions else "none recorded"),
        "Important tool results: " + (" | ".join(state.important_tool_results) if state.important_tool_results else "none recorded"),
        "Modified files: " + (", ".join(state.modified_files) if state.modified_files else "none recorded"),
        "Task status: captured separately in structured session state.",
    ])
    return CompressionResult(Message(MessageRole.SYSTEM, text), len(old))
