"""App-level tests for the Agent Loop tool flow using fake LLM clients."""

import pytest

from mewcode.engine.models import StreamChunk, ToolCall
from mewcode.tui.app import MewCodeApp


class FakeClient:
    def __init__(self, streams):
        self.streams = streams
        self.calls = 0

    async def chat_stream(self, messages, tools=None, **kwargs):
        stream_index = self.calls
        self.calls += 1
        for chunk in self.streams[stream_index]:
            yield chunk

    async def close(self):
        return None


async def _run_message(app: MewCodeApp, pilot, content: str) -> list:
    app._handle_message(content)
    for _ in range(20):
        await pilot.pause(0.1)
        if not app.is_processing:
            break
    return app.conversation_manager.get_messages()


def _role_names(messages: list) -> list[str]:
    return [msg.role.value for msg in messages]


@pytest.mark.asyncio
async def test_read_file_success_flow():
    app = MewCodeApp()
    async with app.run_test() as pilot:
        app.llm_client = FakeClient(
            [
                [
                    StreamChunk(
                        content="",
                        model="fake",
                        finish_reason="tool_calls",
                        tool_calls=[
                            ToolCall(
                                id="call_read",
                                name="ReadFile",
                                input={"path": "config.yaml", "limit": 8},
                            )
                        ],
                    )
                ],
                [
                    StreamChunk(content="final mentions mimo-v2.5-pro", model="fake"),
                    StreamChunk(content="", model="fake", finish_reason="stop"),
                ],
            ]
        )

        messages = await _run_message(app, pilot, "read config")

    tool_messages = [m for m in messages if m.role.value == "tool"]
    assistant_messages = [m for m in messages if m.role.value == "assistant"]

    assert _role_names(messages) == ["user", "assistant", "tool", "assistant"]
    assert app.llm_client.calls == 2
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_result_is_error is False
    assert "default_model" in tool_messages[0].content
    assert "glm-5.2" in tool_messages[0].content
    assert assistant_messages[-1].content == "final mentions mimo-v2.5-pro"


@pytest.mark.asyncio
async def test_missing_file_flow_returns_tool_error_and_final_reply():
    app = MewCodeApp()
    async with app.run_test() as pilot:
        app.llm_client = FakeClient(
            [
                [
                    StreamChunk(
                        content="",
                        model="fake",
                        finish_reason="tool_calls",
                        tool_calls=[
                            ToolCall(
                                id="call_missing",
                                name="ReadFile",
                                input={"path": "missing-file-xyz.txt"},
                            )
                        ],
                    )
                ],
                [
                    StreamChunk(content="final handled missing file", model="fake"),
                    StreamChunk(content="", model="fake", finish_reason="stop"),
                ],
            ]
        )

        messages = await _run_message(app, pilot, "read missing file")

    tool_messages = [m for m in messages if m.role.value == "tool"]
    assistant_messages = [m for m in messages if m.role.value == "assistant"]

    assert _role_names(messages) == ["user", "assistant", "tool", "assistant"]
    assert app.llm_client.calls == 2
    assert tool_messages[0].tool_result_is_error is True
    assert "not found" in tool_messages[0].content.lower()
    assert assistant_messages[-1].content == "final handled missing file"


@pytest.mark.asyncio
async def test_bash_flow_returns_output_and_final_reply():
    app = MewCodeApp()
    app.execution_gateway = None
    async with app.run_test() as pilot:
        app.llm_client = FakeClient(
            [
                [
                    StreamChunk(
                        content="",
                        model="fake",
                        finish_reason="tool_calls",
                        tool_calls=[
                            ToolCall(
                                id="call_bash",
                                name="Bash",
                                input={"command": "echo hello world"},
                            )
                        ],
                    )
                ],
                [
                    StreamChunk(content="final saw hello world", model="fake"),
                    StreamChunk(content="", model="fake", finish_reason="stop"),
                ],
            ]
        )

        messages = await _run_message(app, pilot, "run echo hello world")

    tool_messages = [m for m in messages if m.role.value == "tool"]
    assistant_messages = [m for m in messages if m.role.value == "assistant"]

    assert _role_names(messages) == ["user", "assistant", "tool", "assistant"]
    assert app.llm_client.calls == 2
    assert tool_messages[0].tool_result_is_error is False
    assert "hello world" in tool_messages[0].content.lower()
    assert assistant_messages[-1].content == "final saw hello world"


@pytest.mark.asyncio
async def test_second_response_tool_calls_continue_loop():
    app = MewCodeApp()
    app.execution_gateway = None
    async with app.run_test() as pilot:
        app.llm_client = FakeClient(
            [
                [
                    StreamChunk(
                        content="",
                        model="fake",
                        finish_reason="tool_calls",
                        tool_calls=[
                            ToolCall(
                                id="call_read",
                                name="ReadFile",
                                input={"path": "config.yaml", "limit": 3},
                            )
                        ],
                    )
                ],
                [
                    StreamChunk(content="need one more tool", model="fake"),
                    StreamChunk(
                        content="",
                        model="fake",
                        finish_reason="tool_calls",
                        tool_calls=[
                            ToolCall(
                                id="call_ignored",
                                name="Bash",
                                input={"command": "echo should-not-run"},
                            )
                        ],
                    ),
                ],
                [
                    StreamChunk(content="final after second tool", model="fake"),
                    StreamChunk(content="", model="fake", finish_reason="stop"),
                ],
            ]
        )

        messages = await _run_message(app, pilot, "read then continue")

    tool_messages = [m for m in messages if m.role.value == "tool"]
    assistant_messages = [m for m in messages if m.role.value == "assistant"]

    assert _role_names(messages) == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "assistant",
    ]
    assert app.llm_client.calls == 3
    assert len(tool_messages) == 2
    assert "should-not-run" in tool_messages[1].content
    assert assistant_messages[-1].content == "final after second tool"


@pytest.mark.asyncio
async def test_pure_chat_flow_adds_no_tool_result():
    app = MewCodeApp()
    async with app.run_test() as pilot:
        app.llm_client = FakeClient(
            [
                [
                    StreamChunk(content="plain chat final", model="fake"),
                    StreamChunk(content="", model="fake", finish_reason="stop"),
                ]
            ]
        )

        messages = await _run_message(app, pilot, "hello")

    assert _role_names(messages) == ["user", "assistant"]
    assert app.llm_client.calls == 1
    assert not [m for m in messages if m.role.value == "tool"]
