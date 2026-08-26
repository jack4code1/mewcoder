"""Event models emitted by the Agent Loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .models.metrics import ApiCallMetrics, MetricsSnapshot
from .models.message import TokenUsage


class AgentEventType(str, Enum):
    """Agent event type names consumed by UI and tests."""

    STREAM_TEXT = "stream_text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    TURN_COMPLETE = "turn_complete"
    LOOP_COMPLETE = "loop_complete"
    USAGE = "usage"
    METRICS = "metrics"
    ERROR = "error"
    APPROVAL_REQUIRED = "approval_required"


class AgentStopReason(str, Enum):
    """Why the Agent Loop stopped."""

    MODEL_DONE = "model_done"
    MAX_ITERATIONS = "max_iterations"
    CANCELLED = "cancelled"
    REPEATED_INVALID_TOOLS = "repeated_invalid_tools"
    REPEATED_TOOL_FAILURES = "repeated_tool_failures"
    ERROR = "error"


@dataclass
class AgentEvent:
    """Protocol-neutral event produced by the Agent Loop.

    Optional fields are intentionally kept on a single event class so UI code
    can switch on event_type and read only the fields that matter.
    """

    event_type: AgentEventType
    text: str = ""
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    content: str = ""
    summary: str = ""
    is_error: bool = False
    duration_ms: Optional[int] = None
    turn_index: Optional[int] = None
    total_turns: Optional[int] = None
    stop_reason: Optional[AgentStopReason] = None
    usage: Optional[TokenUsage] = None
    metrics_snapshot: Optional[MetricsSnapshot] = None
    api_call_metrics: Optional[ApiCallMetrics] = None
    message: str = ""
    request_id: Optional[str] = None
    approval: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def stream_text(cls, text: str) -> "AgentEvent":
        return cls(event_type=AgentEventType.STREAM_TEXT, text=text)

    @classmethod
    def tool_use(
        cls, tool_call_id: str, tool_name: str, tool_input: dict[str, Any], summary: str
    ) -> "AgentEvent":
        return cls(
            event_type=AgentEventType.TOOL_USE,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_input=tool_input,
            summary=summary,
        )

    @classmethod
    def tool_result(
        cls,
        tool_call_id: str,
        tool_name: str,
        content: str,
        summary: str,
        is_error: bool,
        duration_ms: int,
    ) -> "AgentEvent":
        return cls(
            event_type=AgentEventType.TOOL_RESULT,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            content=content,
            summary=summary,
            is_error=is_error,
            duration_ms=duration_ms,
        )

    @classmethod
    def turn_complete(cls, turn_index: int) -> "AgentEvent":
        return cls(
            event_type=AgentEventType.TURN_COMPLETE,
            turn_index=turn_index,
        )

    @classmethod
    def loop_complete(
        cls, total_turns: int, stop_reason: AgentStopReason
    ) -> "AgentEvent":
        return cls(
            event_type=AgentEventType.LOOP_COMPLETE,
            total_turns=total_turns,
            stop_reason=stop_reason,
        )

    @classmethod
    def usage(cls, usage: TokenUsage) -> "AgentEvent":
        return cls(event_type=AgentEventType.USAGE, usage=usage)

    @classmethod
    def metrics(cls, snapshot: MetricsSnapshot) -> "AgentEvent":
        return cls(
            event_type=AgentEventType.METRICS,
            usage=snapshot.token_usage,
            metrics_snapshot=snapshot,
            api_call_metrics=snapshot.last_call,
        )

    @classmethod
    def error(cls, message: str) -> "AgentEvent":
        return cls(event_type=AgentEventType.ERROR, message=message, is_error=True)

    @classmethod
    def approval_required(
        cls, tool_name: str, summary: str, request_id: str | None = None,
        approval: dict[str, Any] | None = None,
    ) -> "AgentEvent":
        return cls(
            event_type=AgentEventType.APPROVAL_REQUIRED,
            tool_name=tool_name,
            summary=summary,
            request_id=request_id,
            approval=approval or {},
        )
