"""Shared helpers for OpenAI-compatible adapters.

Three adapters in this project speak the OpenAI Chat Completions wire
format: ``OpenAIAdapter``, ``CustomAdapter`` (any OpenAI-compatible
endpoint), and ``OllamaAdapter`` (its `/api/chat` follows the same
schema). Their tool-calling logic is identical, so the conversion and
streaming-aggregation details live here.

Two responsibilities:

1. ``convert_messages_to_openai`` — turn the project's protocol-neutral
   ``Message`` objects (which keep tool calls in OpenAI-flavoured form
   internally; see plan §核心数据结构) into the dict shape expected by
   the wire format. Handles assistant messages with ``tool_calls`` and
   tool-role messages carrying ``tool_call_id``.

2. ``OpenAIToolCallAggregator`` — accumulate the per-delta ``tool_calls``
   array into a list of ``ToolCall`` objects, then parse the JSON
   ``arguments`` strings on finish. Handles the case where parsing fails
   (returns a ToolCall with ``parse_error`` set so the dispatcher can
   surface a recoverable error to the model).
"""

from __future__ import annotations

import json
from typing import Any

from ..models.message import Message, MessageRole, TokenUsage, ToolCall


def add_stream_usage_option(payload: dict[str, Any]) -> None:
    """Request final streaming usage for OpenAI-compatible endpoints."""
    stream_options = payload.get("stream_options")
    if stream_options is None:
        payload["stream_options"] = {"include_usage": True}
    elif isinstance(stream_options, dict):
        stream_options.setdefault("include_usage", True)


def token_usage_from_openai_usage(usage: dict[str, Any]) -> TokenUsage:
    """Normalize an OpenAI-compatible usage object."""
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    raw_total = usage.get("total_tokens")
    total_tokens = (
        int(raw_total)
        if raw_total is not None
        else prompt_tokens + completion_tokens
    )
    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def convert_messages_to_openai(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert the project's Message list to the OpenAI wire format.

    All four roles are supported. SYSTEM/USER are pass-through. ASSISTANT
    messages may carry ``tool_calls``. TOOL messages carry ``tool_call_id``
    and the result text.
    """
    out: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role == MessageRole.ASSISTANT:
            entry: dict[str, Any] = {
                "role": "assistant",
                "content": msg.content or "",
            }
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.input or {}),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            out.append(entry)
        elif msg.role == MessageRole.TOOL:
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id or "",
                    "content": msg.content or "",
                }
            )
        else:
            # SYSTEM, USER
            out.append({"role": msg.role.value, "content": msg.content or ""})
    return out


class OpenAIToolCallAggregator:
    """Accumulate streaming tool_calls deltas keyed by index.

    Per the OpenAI streaming spec, each ``delta.tool_calls`` entry has an
    ``index`` field; the same index across multiple deltas refers to the
    same tool call. Fields arrive incrementally:

      - ``id`` and ``function.name`` typically arrive once at the start.
      - ``function.arguments`` arrives in JSON-string fragments and must be
        concatenated.

    On ``finalize()`` we attempt ``json.loads`` for each accumulated
    argument string; failures land in ``ToolCall.parse_error`` so the
    dispatcher can return an isError ToolResult to the model rather than
    crashing the stream.
    """

    def __init__(self) -> None:
        self._buf: dict[int, dict[str, str]] = {}

    def has_calls(self) -> bool:
        return bool(self._buf)

    def feed(self, deltas: list[dict[str, Any]]) -> None:
        for delta in deltas:
            idx = delta.get("index")
            if idx is None:
                # Some servers omit index when there's a single call.
                idx = 0
            slot = self._buf.setdefault(
                idx, {"id": "", "name": "", "arguments": ""}
            )
            if "id" in delta and delta["id"]:
                slot["id"] = delta["id"]
            fn = delta.get("function") or {}
            if "name" in fn and fn["name"]:
                slot["name"] = fn["name"]
            if "arguments" in fn and fn["arguments"] is not None:
                slot["arguments"] += fn["arguments"]

    def finalize(self) -> list[ToolCall]:
        results: list[ToolCall] = []
        for idx in sorted(self._buf.keys()):
            slot = self._buf[idx]
            args_str = slot["arguments"] or ""
            parse_error: str | None = None
            parsed: dict[str, Any] = {}
            if args_str.strip() == "":
                parsed = {}
            else:
                try:
                    loaded = json.loads(args_str)
                    if isinstance(loaded, dict):
                        parsed = loaded
                    else:
                        parse_error = (
                            f"tool arguments must be a JSON object, got {type(loaded).__name__}"
                        )
                except json.JSONDecodeError as e:
                    parse_error = f"failed to parse tool arguments JSON: {e.msg}"
            results.append(
                ToolCall(
                    id=slot["id"] or f"tool_call_{idx}",
                    name=slot["name"] or "",
                    input=parsed,
                    parse_error=parse_error,
                )
            )
        return results
