"""Deterministic session state kept separate from lossy conversation summaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..models.message import Message, MessageRole


@dataclass
class SessionState:
    """Facts that must survive history compression without LLM interpretation."""

    goal: str = ""
    key_decisions: list[str] = field(default_factory=list)
    important_tool_results: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    task_status: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_prompt(self) -> str:
        lines = [
            "Structured session state:",
            "Current workspace, tool observations, and test results take precedence over historical decisions.",
        ]
        if self.goal:
            lines.append(f"Goal: {self.goal}")
        if self.key_decisions:
            lines.append("Historical decisions (verify before relying on them): " + " | ".join(self.key_decisions[-4:]))
        if self.modified_files:
            lines.append("Modified files: " + ", ".join(self.modified_files[-12:]))
        if self.task_status:
            lines.append("Task status: " + ", ".join(f"{key}={value}" for key, value in self.task_status.items()))
        if self.important_tool_results:
            lines.append("Recent external observations: " + " | ".join(self.important_tool_results[-4:]))
        return "\n".join(lines)


def build_session_state(messages: list[Message], task_status: dict[str, str] | None = None) -> SessionState:
    """Extract stable execution facts without asking an LLM to summarize them."""
    calls = {
        call.id: call
        for message in messages
        if message.role is MessageRole.ASSISTANT
        for call in (message.tool_calls or [])
    }
    users = [message.content.strip() for message in messages if message.role is MessageRole.USER and message.content.strip()]
    decisions = [
        message.content.strip().replace("\n", " ")[:240]
        for message in messages
        if message.role is MessageRole.ASSISTANT and message.content.strip() and not message.tool_calls
    ]
    modified_files: list[str] = []
    tool_results: list[str] = []
    for message in messages:
        if message.role is not MessageRole.TOOL:
            continue
        call = calls.get(message.tool_call_id or "")
        if call and call.name in {"WriteFile", "EditFile"}:
            path = call.input.get("path")
            if isinstance(path, str) and path not in modified_files and not message.tool_result_is_error:
                modified_files.append(path)
        if message.tool_result_is_error or (call and call.name in {"WriteFile", "EditFile", "Bash"}):
            tool_name = call.name if call else "Tool"
            status = "error" if message.tool_result_is_error else "ok"
            tool_results.append(f"{tool_name} ({status}): {message.content.replace(chr(10), ' ')[:220]}")
    return SessionState(
        goal=users[-1] if users else "",
        key_decisions=decisions[-4:],
        important_tool_results=tool_results[-6:],
        modified_files=modified_files,
        task_status=dict(task_status or {}),
    )


def compact_tool_results_for_context(
    messages: list[Message], max_chars: int = 1_200
) -> list[Message]:
    """Bound tool observations for a model request without mutating history.

    Tool output can be valuable evidence but is not all equally valuable to the
    next decision.  Keep short results intact; for large results retain both
    the leading context and trailing diagnostics, where command errors commonly
    appear.  The original Message remains in the persisted conversation.
    """
    compacted: list[Message] = []
    limit = max(200, max_chars)
    for message in messages:
        if message.role is not MessageRole.TOOL or len(message.content) <= limit:
            compacted.append(message)
            continue
        head_size = limit * 2 // 3
        tail_size = limit - head_size
        content = (
            f"[Tool result condensed for context; original retained in session. "
            f"{len(message.content)} chars total]\n"
            f"{message.content[:head_size]}\n... [omitted] ...\n{message.content[-tail_size:]}"
        )
        compacted.append(
            Message(
                role=message.role,
                content=content,
                timestamp=message.timestamp,
                token_usage=message.token_usage,
                metadata=message.metadata,
                tool_calls=message.tool_calls,
                tool_call_id=message.tool_call_id,
                tool_result_is_error=message.tool_result_is_error,
            )
        )
    return compacted
