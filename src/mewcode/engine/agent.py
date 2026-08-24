"""ReAct-style Agent Loop for multi-turn tool use."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Optional

from .agent_events import AgentEvent, AgentStopReason
from .conversation import ConversationManager
from .models.client import LLMClient
from .models.metrics import ApiCallMetrics, MetricsAggregate, MetricsSnapshot
from .models.message import Message, MessageRole, TokenUsage, ToolCall
from .tools import ToolRegistry, ToolResult
from .security.gateway import ExecutionGateway
from .security.models import ExecutionRequest
from .context import plan_messages
from .extensions.hooks import HookRunner


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
    registry: ToolRegistry, call: ToolCall, gateway: ExecutionGateway | None = None
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
            tool = registry.get(call.name)
            if gateway is not None and tool is not None:
                result = await gateway.execute(
                    ExecutionRequest(
                        tool_name=call.name,
                        input=call.input,
                        request_id=call.id,
                        operation=tool.operation_kind,
                        risk=tool.risk_level,
                    )
                )
            else:
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
    gateway: ExecutionGateway | None = None,
) -> list[tuple[ToolCall, ToolResult, int]]:
    if not batch.is_concurrency_safe:
        results = []
        for call in batch.calls:
            results.append(await _execute_tool_call(registry, call, gateway))
        return results

    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def run_one(call: ToolCall) -> tuple[ToolCall, ToolResult, int]:
        async with semaphore:
            return await _execute_tool_call(registry, call, gateway)

    return list(await asyncio.gather(*(run_one(call) for call in batch.calls)))


def _has_usage(usage: TokenUsage) -> bool:
    return bool(usage.prompt_tokens or usage.completion_tokens or usage.total_tokens)


def _metrics_snapshot(
    conversation_manager: ConversationManager,
    last_call: Optional[ApiCallMetrics] = None,
) -> MetricsSnapshot:
    aggregate = MetricsAggregate.from_dict(
        conversation_manager.get_api_metrics().to_dict()
    )
    usage = conversation_manager.get_token_usage()
    visible_usage = None
    if _has_usage(usage) or aggregate.usage_call_count > 0:
        visible_usage = TokenUsage(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )
    return MetricsSnapshot(
        token_usage=visible_usage,
        api_metrics=aggregate,
        last_call=last_call,
    )


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
    execution_gateway: ExecutionGateway | None = None,
    context_budget: int | None = None,
    hook_runner: HookRunner | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> AsyncIterator[AgentEvent]:
    """Run the ReAct loop and emit progress events.

    The caller is responsible for adding the user message before invoking the
    loop. This function owns assistant/tool message persistence afterwards.
    """
    total_usage = conversation_manager.get_token_usage()
    consecutive_invalid_tools = 0

    if hook_runner is not None:
        for hook in await hook_runner.run("task_start"):
            if not hook.success:
                yield AgentEvent.error(f"Hook {hook.name} failed: {hook.message}")
                return

    for turn_index in range(1, max_iterations + 1):
        if cancel_event is not None and cancel_event.is_set():
            yield AgentEvent.loop_complete(turn_index - 1, AgentStopReason.CANCELLED)
            return

        assistant_text = ""
        pending_tool_calls: list[ToolCall] = []
        turn_usage = TokenUsage()
        usage_seen = False
        request_started_at = clock()
        first_token_at: Optional[float] = None

        try:
            messages = build_messages()
            if context_budget is not None:
                messages, context_plan = plan_messages(messages, context_budget)
                active = conversation_manager.get_active_conversation()
                if active is not None:
                    active.context_metadata = {
                        "budget": context_plan.budget,
                        "used_tokens": context_plan.used_tokens,
                        "excluded_sources": [item.source for item in context_plan.excluded],
                    }
            async for chunk in llm_client.chat_stream(messages, tools=tools_payload):
                if cancel_event is not None and cancel_event.is_set():
                    yield AgentEvent.loop_complete(
                        turn_index - 1, AgentStopReason.CANCELLED
                    )
                    return
                if chunk.content:
                    if first_token_at is None:
                        first_token_at = clock()
                    assistant_text += chunk.content
                    yield AgentEvent.stream_text(chunk.content)
                if chunk.token_usage is not None:
                    usage_seen = True
                    turn_usage = turn_usage + chunk.token_usage
                    total_usage = total_usage + chunk.token_usage
                    yield AgentEvent.usage(total_usage)
                if chunk.tool_calls:
                    pending_tool_calls = list(chunk.tool_calls)
            request_completed_at = clock()
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
                token_usage=turn_usage if usage_seen else None,
            )
        )
        call_metrics = ApiCallMetrics.from_timing(
            usage=turn_usage if usage_seen else None,
            started_at=request_started_at,
            completed_at=request_completed_at,
            first_token_at=first_token_at,
        )
        conversation_manager.add_api_call_metrics(call_metrics)
        yield AgentEvent.metrics(_metrics_snapshot(conversation_manager, call_metrics))
        yield AgentEvent.turn_complete(turn_index)

        if not pending_tool_calls:
            if hook_runner is not None:
                await hook_runner.run("task_complete")
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

            results = await _run_batch(
                batch, tool_registry, max_concurrency, execution_gateway
            )
            for call, result, duration_ms in results:
                if result.metadata.get("reason") == "approval_required":
                    yield AgentEvent.approval_required(
                        call.name,
                        summarize_tool_input(call.name, call.input),
                        result.metadata.get("request_id"),
                        result.metadata.get("approval"),
                    )
                    request_id = result.metadata.get("request_id")
                    if execution_gateway is not None and request_id:
                        if cancel_event is not None and cancel_event.is_set():
                            execution_gateway.cancel_pending()
                        result = await execution_gateway.wait_for_approval(request_id)
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
