"""ReAct-style Agent Loop for multi-turn tool use."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Optional

from .agent_events import AgentEvent, AgentStopReason
from .conversation import ConversationManager
from .models.client import LLMClient
from .models.message import Message, MessageRole, TokenUsage, ToolCall
from .tools import ToolRegistry, ToolResult


def summarize_tool_input(name: str, input: dict) -> str:
    """Produce a short display summary for a tool call."""
    if not isinstance(input, dict):
        return ""
    if name in {"ReadFile", "WriteFile", "EditFile"}:
        return str(input.get("path", ""))
    if name == "Bash":
        cmd = str(input.get("command", ""))
        return cmd[:60] + ("..." if len(cmd) > 60 else "")
    if name == "Glob":
        return str(input.get("pattern", ""))
    if name == "Grep":
        return str(input.get("pattern", ""))
    for value in input.values():
        if isinstance(value, (str, int, float, bool)):
            text = str(value)
            return text[:60] + ("..." if len(text) > 60 else "")
    return ""


def summarize_tool_result(content: str) -> str:
    """Return a short first-line summary for UI traces."""
    if not content:
        return ""
    line = content.splitlines()[0].strip()
    return line[:80] + ("..." if len(line) > 80 else "")


@dataclass
class ToolBatch:
    """A batch of tool calls that can be executed together."""

    is_concurrency_safe: bool
    calls: list[ToolCall]


def partition_tool_calls(
    tool_calls: list[ToolCall], registry: ToolRegistry
) -> list[ToolBatch]:
    """Partition calls into consecutive concurrent-safe and serial batches."""
    batches: list[ToolBatch] = []
    for call in tool_calls:
        tool = registry.get(call.name)
        safe = bool(tool is not None and getattr(tool, "is_concurrency_safe", False))
        if safe and batches and batches[-1].is_concurrency_safe:
            batches[-1].calls.append(call)
        else:
            batches.append(ToolBatch(is_concurrency_safe=safe, calls=[call]))
    return batches


async def _execute_tool_call(
    registry: ToolRegistry, call: ToolCall
) -> tuple[ToolCall, ToolResult, int]:
    start = time.monotonic()
    if call.parse_error:
        result = ToolResult(
            content=f"Tool arguments could not be parsed: {call.parse_error}",
            is_error=True,
            metadata={"tool": call.name, "reason": "parse_error"},
        )
    else:
        try:
            result = await registry.execute(call.name, call.input)
        except Exception as e:  # noqa: BLE001  surface as agent-visible error
            result = ToolResult(
                content=f"Tool dispatch failed: {e}",
                is_error=True,
                metadata={"tool": call.name, "reason": "exception"},
            )
    duration_ms = int((time.monotonic() - start) * 1000)
    result.metadata.setdefault("duration_ms", duration_ms)
    result.metadata.setdefault("tool", call.name)
    return call, result, int(result.metadata.get("duration_ms", duration_ms))


async def _run_batch(
    batch: ToolBatch,
    registry: ToolRegistry,
    max_concurrency: int,
) -> list[tuple[ToolCall, ToolResult, int]]:
    if not batch.is_concurrency_safe:
        results = []
        for call in batch.calls:
            results.append(await _execute_tool_call(registry, call))
        return results

    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def run_one(call: ToolCall) -> tuple[ToolCall, ToolResult, int]:
        async with semaphore:
            return await _execute_tool_call(registry, call)

    return list(await asyncio.gather(*(run_one(call) for call in batch.calls)))


def _has_usage(usage: TokenUsage) -> bool:
    return bool(usage.prompt_tokens or usage.completion_tokens or usage.total_tokens)


async def run_agent_loop(
    *,
    llm_client: LLMClient,
    conversation_manager: ConversationManager,
    tool_registry: ToolRegistry,
    tools_payload: list[dict],
    build_messages: Callable[[], list[Message]],
    max_iterations: int = 50,
    invalid_tool_limit: int = 3,
    max_concurrency: int = 4,
    cancel_event: Optional[asyncio.Event] = None,
) -> AsyncIterator[AgentEvent]:
    """Run the ReAct loop and emit progress events.

    The caller is responsible for adding the user message before invoking the
    loop. This function owns assistant/tool message persistence afterwards.
    """
    total_usage = TokenUsage()
    consecutive_invalid_tools = 0

    for turn_index in range(1, max_iterations + 1):
        if cancel_event is not None and cancel_event.is_set():
            yield AgentEvent.loop_complete(turn_index - 1, AgentStopReason.CANCELLED)
            return

        assistant_text = ""
        pending_tool_calls: list[ToolCall] = []
        turn_usage = TokenUsage()

        try:
            async for chunk in llm_client.chat_stream(
                build_messages(), tools=tools_payload
            ):
                if cancel_event is not None and cancel_event.is_set():
                    yield AgentEvent.loop_complete(
                        turn_index - 1, AgentStopReason.CANCELLED
                    )
                    return
                if chunk.content:
                    assistant_text += chunk.content
                    yield AgentEvent.stream_text(chunk.content)
                if chunk.token_usage:
                    turn_usage = turn_usage + chunk.token_usage
                    total_usage = total_usage + chunk.token_usage
                    yield AgentEvent.usage(total_usage)
                if chunk.tool_calls:
                    pending_tool_calls = list(chunk.tool_calls)
        except asyncio.CancelledError:
            yield AgentEvent.loop_complete(turn_index - 1, AgentStopReason.CANCELLED)
            return
        except Exception as e:  # noqa: BLE001
            yield AgentEvent.error(f"LLM call failed: {e}")
            yield AgentEvent.loop_complete(turn_index - 1, AgentStopReason.ERROR)
            return

        conversation_manager.add_message(
            Message(
                role=MessageRole.ASSISTANT,
                content=assistant_text,
                tool_calls=pending_tool_calls or None,
                token_usage=turn_usage if _has_usage(turn_usage) else None,
            )
        )
        yield AgentEvent.turn_complete(turn_index)

        if not pending_tool_calls:
            yield AgentEvent.loop_complete(turn_index, AgentStopReason.MODEL_DONE)
            return

        for call in pending_tool_calls:
            yield AgentEvent.tool_use(
                call.id,
                call.name,
                call.input,
                summarize_tool_input(call.name, call.input),
            )

        batches = partition_tool_calls(pending_tool_calls, tool_registry)
        for batch in batches:
            if cancel_event is not None and cancel_event.is_set():
                yield AgentEvent.loop_complete(turn_index, AgentStopReason.CANCELLED)
                return

            results = await _run_batch(batch, tool_registry, max_concurrency)
            for call, result, duration_ms in results:
                conversation_manager.add_message(
                    Message(
                        role=MessageRole.TOOL,
                        content=result.content,
                        tool_call_id=call.id,
                        tool_result_is_error=bool(result.is_error),
                    )
                )
                yield AgentEvent.tool_result(
                    call.id,
                    call.name,
                    result.content,
                    summarize_tool_result(result.content),
                    bool(result.is_error),
                    duration_ms,
                )

                if result.is_error and result.metadata.get("reason") == "not_registered":
                    consecutive_invalid_tools += 1
                else:
                    consecutive_invalid_tools = 0

                if consecutive_invalid_tools >= invalid_tool_limit:
                    yield AgentEvent.error(
                        "Agent stopped after repeated unknown or disabled tool requests."
                    )
                    yield AgentEvent.loop_complete(
                        turn_index, AgentStopReason.REPEATED_INVALID_TOOLS
                    )
                    return

    yield AgentEvent.error(
        f"Agent reached the maximum iteration limit ({max_iterations}) and stopped."
    )
    yield AgentEvent.loop_complete(max_iterations, AgentStopReason.MAX_ITERATIONS)
