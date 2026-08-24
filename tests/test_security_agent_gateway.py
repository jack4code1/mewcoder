import asyncio

import pytest

from mewcode.engine.agent import run_agent_loop
from mewcode.engine.agent_events import AgentEventType
from mewcode.engine.conversation import ConversationManager
from mewcode.engine.models import Message, MessageRole, StreamChunk, ToolCall
from mewcode.engine.security.gateway import ExecutionGateway
from mewcode.engine.tools import ToolContext, ToolRegistry, WriteFileTool


class FakeClient:
    def __init__(self):
        self.calls = 0

    async def chat_stream(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            yield StreamChunk(
                content="",
                model="fake",
                tool_calls=[ToolCall(id="write-1", name="WriteFile", input={"path": "done.txt", "content": "ok"})],
            )
        else:
            yield StreamChunk(content="complete", model="fake")


@pytest.mark.asyncio
async def test_approved_request_continues_the_same_agent_loop(tmp_path):
    manager = ConversationManager(storage_dir=str(tmp_path / "sessions"))
    manager.create_conversation()
    manager.add_message(Message(role=MessageRole.USER, content="write it"))
    registry = ToolRegistry(ToolContext.detect(tmp_path))
    registry.register(WriteFileTool())
    gateway = ExecutionGateway(registry)
    loop = run_agent_loop(
        llm_client=FakeClient(),
        conversation_manager=manager,
        tool_registry=registry,
        tools_payload=[],
        build_messages=lambda: manager.get_messages(),
        execution_gateway=gateway,
    )

    observed = []
    async for event in loop:
        observed.append(event)
        if event.event_type is AgentEventType.APPROVAL_REQUIRED:
            assert event.request_id is not None
            assert not (tmp_path / "done.txt").exists()
            await gateway.approve(event.request_id)

    tool_messages = [message for message in manager.get_messages() if message.role is MessageRole.TOOL]
    assert tool_messages and not tool_messages[0].tool_result_is_error, (
        tool_messages,
        [(event.event_type, event.message) for event in observed],
    )
    assert (tmp_path / "done.txt").read_text(encoding="utf-8") == "ok"
    assert [event.event_type for event in observed].count(AgentEventType.TURN_COMPLETE) == 2
    assert observed[-1].event_type is AgentEventType.LOOP_COMPLETE
    assert [message.role for message in manager.get_messages()] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
        MessageRole.TOOL,
        MessageRole.ASSISTANT,
    ]
