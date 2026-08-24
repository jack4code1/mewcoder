"""Loss-aware history compression helpers."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.message import Message, MessageRole


@dataclass(frozen=True)
class CompressionResult:
    summary: Message
    source_count: int
    degraded: bool = False


def compress_messages(messages: list[Message], keep_recent: int = 8) -> CompressionResult | None:
    """Create a deterministic fallback summary; original messages remain stored."""
    old = messages[:-keep_recent] if len(messages) > keep_recent else []
    if not old:
        return None
    text = "\n".join(f"{message.role.value}: {message.content[:240]}" for message in old)
    return CompressionResult(Message(MessageRole.SYSTEM, f"Conversation summary ({len(old)} messages):\n{text}"), len(old))
