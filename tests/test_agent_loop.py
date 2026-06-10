import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from mewcode.engine.agent import partition_tool_calls, run_agent_loop
from mewcode.engine.agent_events import AgentEventType, AgentStopReason
from mewcode.engine.conversation import ConversationManager
from mewcode.engine.models import Message, MessageRole, StreamChunk, ToolCall
from mewcode.engine.tools import Tool, ToolContext, ToolRegistry, ToolResult


class FakeClient:
    def __init__(self, streams):
        self.streams = streams
        self.calls = 0
        self.seen_messages = []

    async def chat_stream(self, messages, tools=None, **kwargs):
        self.seen_messages.append(messages)
        stream = self.streams[self.calls]
        self.calls += 1
        for chunk in stream:
            yield chunk


class EchoTool(Tool):
    name = "Echo"
    description = "Echo a value."
    input_schema = {"type": "object"}
    is_concurrency_safe = True
    is_read_only = True

    async def execute(self, ctx: ToolContext, input: dict) -> ToolResult:
        return ToolResult(content=f"echo:{input.get('value', '')}")


class UnsafeTool(Tool):
    name = "Unsafe"
    description = "Unsafe tool."
    input_schema = {"type": "object"}
    is_concurrency_safe = False

    async def execute(self, ctx: ToolContext, input: dict) -> ToolResult:
        return ToolResult(content="unsafe")


def _workspace_test_dir() -> Path:
    path = Path.cwd() / ".mewcode_test_sessions" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manager() -> ConversationManager:
    manager = ConversationManager(storage_dir=str(_workspace_test_dir()))
    manager.create_conversation()
    manager.add_message(Message(role=MessageRole.USER, content="do it"))
    return manager


def _registry() -> ToolRegistry:
    registry = ToolRegistry(ToolContext.detect(Path.cwd()))
    registry.register(EchoTool())
    registry.register(UnsafeTool())
    return registry


def _messages(manager: ConversationManager):
    return [Message(role=MessageRole.SYSTEM, content="system")] + manager.get_messages()


async def _collect(loop):
    return [event async for event in loop]


@pytest.mark.asyncio
async def test_terminal_no_tool_response():
    manager = _manager()
    registry = _registry()
    client = FakeClient(
        [[StreamChunk(content="final", model="fake", finish_reason="stop")]]
    )

    events = await _collect(
        run_agent_loop(
            llm_client=client,
            conversation_manager=manager,
            tool_registry=registry,
            tools_payload=[],
            build_messages=lambda: _messages(manager),
        )
    )

    assert [e.event_type for e in events] == [
        AgentEventType.STREAM_TEXT,
        AgentEventType.METRICS,
        AgentEventType.TURN_COMPLETE,
        AgentEventType.LOOP_COMPLETE,
    ]
    assert events[-1].stop_reason == AgentStopReason.MODEL_DONE
    assert [m.role.value for m in manager.get_messages()] == ["user", "assistant"]
    assert manager.get_messages()[-1].content == "final"
    assert client.calls == 1


@pytest.mark.asyncio
async def test_multi_turn_tool_loop():
    manager = _manager()
    registry = _registry()
    client = FakeClient(
        [
            [
                StreamChunk(
                    content="need echo",
                    model="fake",
                    tool_calls=[
                        ToolCall(id="call_1", name="Echo", input={"value": "one"})
                    ],
                )
            ],
            [
                StreamChunk(
                    content="need echo again",
                    model="fake",
                    tool_calls=[
                        ToolCall(id="call_2", name="Echo", input={"value": "two"})
                    ],
                )
            ],
            [StreamChunk(content="done", model="fake", finish_reason="stop")],
        ]
    )

    events = await _collect(
        run_agent_loop(
            llm_client=client,
            conversation_manager=manager,
            tool_registry=registry,
            tools_payload=[],
            build_messages=lambda: _messages(manager),
        )
    )

    assert client.calls == 3
    assert [m.role.value for m in manager.get_messages()] == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "assistant",
    ]
    assert [m.tool_call_id for m in manager.get_messages() if m.role == MessageRole.TOOL] == [
        "call_1",
        "call_2",
    ]
    assert sum(e.event_type == AgentEventType.TOOL_USE for e in events) == 2
    assert events[-1].stop_reason == AgentStopReason.MODEL_DONE


@pytest.mark.asyncio
async def test_repeated_unknown_tool_stops():
    manager = _manager()
    registry = _registry()
    client = FakeClient(
        [
            [
                StreamChunk(
                    content="",
                    model="fake",
                    tool_calls=[ToolCall(id="bad_1", name="Missing", input={})],
                )
            ],
            [
                StreamChunk(
                    content="",
                    model="fake",
                    tool_calls=[ToolCall(id="bad_2", name="Missing", input={})],
                )
            ],
            [
                StreamChunk(
                    content="",
                    model="fake",
                    tool_calls=[ToolCall(id="bad_3", name="Missing", input={})],
                )
            ],
            [StreamChunk(content="should not run", model="fake")],
        ]
    )

    events = await _collect(
        run_agent_loop(
            llm_client=client,
            conversation_manager=manager,
            tool_registry=registry,
            tools_payload=[],
            build_messages=lambda: _messages(manager),
            invalid_tool_limit=3,
        )
    )

    assert client.calls == 3
    assert events[-1].stop_reason == AgentStopReason.REPEATED_INVALID_TOOLS
    assert any(e.event_type == AgentEventType.ERROR for e in events)


@pytest.mark.asyncio
async def test_max_iterations_stop():
    manager = _manager()
    registry = _registry()
    client = FakeClient(
        [
            [
                StreamChunk(
                    content="",
                    model="fake",
                    tool_calls=[ToolCall(id="call_1", name="Echo", input={})],
                )
            ],
            [
                StreamChunk(
                    content="",
                    model="fake",
                    tool_calls=[ToolCall(id="call_2", name="Echo", input={})],
                )
            ],
        ]
    )

    events = await _collect(
        run_agent_loop(
            llm_client=client,
            conversation_manager=manager,
            tool_registry=registry,
            tools_payload=[],
            build_messages=lambda: _messages(manager),
            max_iterations=2,
        )
    )

    assert client.calls == 2
    assert events[-1].stop_reason == AgentStopReason.MAX_ITERATIONS
    assert any(e.event_type == AgentEventType.ERROR for e in events)


@pytest.mark.asyncio
async def test_cancel_before_first_turn():
    manager = _manager()
    registry = _registry()
    client = FakeClient([[StreamChunk(content="should not run", model="fake")]])
    cancel_event = asyncio.Event()
    cancel_event.set()

    events = await _collect(
        run_agent_loop(
            llm_client=client,
            conversation_manager=manager,
            tool_registry=registry,
            tools_payload=[],
            build_messages=lambda: _messages(manager),
            cancel_event=cancel_event,
        )
    )

    assert client.calls == 0
    assert events[-1].stop_reason == AgentStopReason.CANCELLED


def test_partition_tool_calls_batches():
    registry = _registry()
    calls = [
        ToolCall(id="r1", name="Echo", input={}),
        ToolCall(id="r2", name="Echo", input={}),
        ToolCall(id="w1", name="Unsafe", input={}),
        ToolCall(id="r3", name="Echo", input={}),
    ]

    batches = partition_tool_calls(calls, registry)

    assert [batch.is_concurrency_safe for batch in batches] == [True, False, True]
    assert [[call.id for call in batch.calls] for batch in batches] == [
        ["r1", "r2"],
        ["w1"],
        ["r3"],
    ]
