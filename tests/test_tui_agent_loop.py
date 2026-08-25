import pytest

from mewcode.engine.models import StreamChunk, ToolCall
from mewcode.tui.app import MewCodeApp


class FakeClient:
    def __init__(self, streams):
        self.streams = streams
        self.calls = 0

    async def chat_stream(self, messages, tools=None, **kwargs):
        stream = self.streams[self.calls]
        self.calls += 1
        for chunk in stream:
            yield chunk

    async def close(self):
        return None


async def _run_message(app: MewCodeApp, pilot, content: str) -> list:
    app._handle_message(content)
    for _ in range(30):
        await pilot.pause(0.1)
        if not app.is_processing:
            break
    return app.conversation_manager.get_messages()


@pytest.mark.asyncio
async def test_tui_consumes_agent_loop_events_for_multiple_tool_rounds():
    app = MewCodeApp()
    app.execution_gateway = None
    async with app.run_test() as pilot:
        app.llm_client = FakeClient(
            [
                [
                    StreamChunk(
                        content="",
                        model="fake",
                        tool_calls=[
                            ToolCall(
                                id="read",
                                name="ReadFile",
                                input={"path": "config.yaml", "limit": 3},
                            )
                        ],
                    )
                ],
                [
                    StreamChunk(
                        content="",
                        model="fake",
                        tool_calls=[
                            ToolCall(
                                id="bash",
                                name="Bash",
                                input={"command": "echo second-round"},
                            )
                        ],
                    )
                ],
                [
                    StreamChunk(content="done", model="fake"),
                    StreamChunk(content="", model="fake", finish_reason="stop"),
                ],
            ]
        )

        messages = await _run_message(app, pilot, "multi turn")

    assert app.llm_client.calls == 3
    assert [m.role.value for m in messages] == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "assistant",
    ]
    tool_messages = [m for m in messages if m.role.value == "tool"]
    assert len(tool_messages) == 2
    assert "second-round" in tool_messages[1].content
