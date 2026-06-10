from pathlib import Path
from uuid import uuid4

import pytest

from mewcode.engine.agent import run_agent_loop
from mewcode.engine.agent_events import AgentEventType
from mewcode.engine.conversation import ConversationManager
from mewcode.engine.models import Message, MessageRole, StreamChunk, TokenUsage
from mewcode.engine.tools import ToolContext, ToolRegistry


class FakeClient:
    def __init__(self, streams):
        self.streams = streams
        self.calls = 0

    async def chat_stream(self, messages, tools=None, **kwargs):
        stream = self.streams[self.calls]
        self.calls += 1
        for chunk in stream:
            yield chunk


class FakeClock:
    def __init__(self, times):
        self.times = list(times)

    def __call__(self):
        return self.times.pop(0)


def _workspace_test_dir() -> Path:
    path = Path.cwd() / ".mewcode_test_sessions" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manager() -> ConversationManager:
    manager = ConversationManager(storage_dir=str(_workspace_test_dir()))
    manager.create_conversation()
    manager.add_message(Message(role=MessageRole.USER, content="measure"))
    return manager


def _registry() -> ToolRegistry:
    return ToolRegistry(ToolContext.detect(Path.cwd()))


def _messages(manager: ConversationManager):
    return [Message(role=MessageRole.SYSTEM, content="system")] + manager.get_messages()


async def _collect(loop):
    return [event async for event in loop]


@pytest.mark.asyncio
async def test_agent_loop_emits_token_and_api_metrics():
    manager = _manager()
    client = FakeClient(
        [
            [
                StreamChunk(content="hello", model="fake"),
                StreamChunk(
                    content="",
                    model="fake",
                    finish_reason="stop",
                    token_usage=TokenUsage(
                        prompt_tokens=10,
                        completion_tokens=20,
                        total_tokens=30,
                    ),
                ),
            ]
        ]
    )

    events = await _collect(
        run_agent_loop(
            llm_client=client,
            conversation_manager=manager,
            tool_registry=_registry(),
            tools_payload=[],
            build_messages=lambda: _messages(manager),
            clock=FakeClock([0.0, 0.5, 2.5]),
        )
    )

    usage_events = [e for e in events if e.event_type == AgentEventType.USAGE]
    metrics_events = [e for e in events if e.event_type == AgentEventType.METRICS]

    assert usage_events[-1].usage.total_tokens == 30
    assert len(metrics_events) == 1
    call = metrics_events[0].api_call_metrics
    assert call.ttft_ms == 500
    assert call.latency_ms == 2500
    assert call.output_tokens_per_second == 10.0
    assert manager.get_token_usage().total_tokens == 30
    assert manager.get_api_metrics().average_output_tokens_per_second == 10.0


@pytest.mark.asyncio
async def test_agent_loop_missing_usage_keeps_token_usage_unavailable():
    manager = _manager()
    client = FakeClient([[StreamChunk(content="hello", model="fake", finish_reason="stop")]])

    events = await _collect(
        run_agent_loop(
            llm_client=client,
            conversation_manager=manager,
            tool_registry=_registry(),
            tools_payload=[],
            build_messages=lambda: _messages(manager),
            clock=FakeClock([1.0, 1.1, 2.0]),
        )
    )

    metrics_event = [e for e in events if e.event_type == AgentEventType.METRICS][0]

    assert not [e for e in events if e.event_type == AgentEventType.USAGE]
    assert metrics_event.metrics_snapshot.token_usage is None
    assert metrics_event.api_call_metrics.ttft_ms == 100
    assert metrics_event.api_call_metrics.latency_ms == 1000
    assert metrics_event.api_call_metrics.output_tokens_per_second is None
    assert manager.get_api_metrics().usage_call_count == 0
