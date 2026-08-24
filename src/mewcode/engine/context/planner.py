"""Deterministic context selection before a model request."""

from __future__ import annotations

from dataclasses import dataclass, field
from ..models.message import Message


@dataclass(frozen=True)
class ContextItem:
    source: str
    content: str
    priority: int = 0
    token_estimate: int = 0


@dataclass(frozen=True)
class ContextPlan:
    included: list[ContextItem] = field(default_factory=list)
    excluded: list[ContextItem] = field(default_factory=list)
    budget: int = 0

    @property
    def used_tokens(self) -> int:
        return sum(item.token_estimate for item in self.included)


def plan_context(items: list[ContextItem], budget: int) -> ContextPlan:
    """Keep highest-priority items that fit the explicit token budget."""
    included: list[ContextItem] = []
    excluded: list[ContextItem] = []
    used = 0
    for item in sorted(items, key=lambda value: value.priority, reverse=True):
        if item.token_estimate <= max(0, budget - used):
            included.append(item)
            used += item.token_estimate
        else:
            excluded.append(item)
    return ContextPlan(included=included, excluded=excluded, budget=budget)


def estimate_tokens(content: str) -> int:
    """Conservative deterministic estimate used when provider counts are absent."""
    return max(1, (len(content) + 3) // 4)


def plan_messages(messages: list[Message], budget: int) -> tuple[list[Message], ContextPlan]:
    """Build an immutable request snapshot while retaining message roles."""
    items = [
        ContextItem(f"message:{index}", message.content, 100 if message.role.value == "system" else index,
                    estimate_tokens(message.content))
        for index, message in enumerate(messages)
    ]
    plan = plan_context(items, budget)
    allowed = {item.source for item in plan.included}
    selected = [message for index, message in enumerate(messages) if f"message:{index}" in allowed]
    # Preserve a traceable compact representation when history was excluded.
    if plan.excluded:
        from .compression import compress_messages
        compressed = compress_messages(messages, keep_recent=len(selected))
        if compressed is not None:
            selected.insert(1 if selected and selected[0].role.value == "system" else 0, compressed.summary)
    return selected, plan
