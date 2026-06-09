"""Tests for ClaudeAdapter (Anthropic) tool_use streaming aggregation.

Same approach as test_adapter_tool_calls.py: feed pre-canned SSE through a
fake httpx.AsyncClient.stream context manager and assert on the StreamChunk
sequence the adapter produces.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Iterable

import pytest

from mewcode.engine.adapters.claude_adapter import ClaudeAdapter
from mewcode.engine.models import Message, MessageRole


class _FakeStreamResponse:
    def __init__(self, chunks: Iterable[bytes]):
        self._chunks = list(chunks)

    def raise_for_status(self) -> None:
        return None

    async def aiter_bytes(self):
        for c in self._chunks:
            yield c


def _install_fake_stream(adapter, sse_chunks: list[bytes], captured: dict | None = None):
    @asynccontextmanager
    async def fake_stream(method, url, json=None):
        if captured is not None:
            captured["payload"] = json
        yield _FakeStreamResponse(sse_chunks)

    adapter.client.stream = fake_stream  # type: ignore[assignment]


def _sse(event: str, data: str) -> bytes:
    return f"event: {event}\ndata: {data}\n".encode("utf-8")


@pytest.fixture
def adapter() -> ClaudeAdapter:
    return ClaudeAdapter(
        model="claude-3-5-sonnet-20241022",
        api_key="dummy",
        base_url="https://example.test",
    )


class TestAnthropicStreamingTextOnly:
    @pytest.mark.asyncio
    async def test_text_only(self, adapter):
        sse = [
            _sse("message_start", '{"type":"message_start","message":{"model":"claude","usage":{"input_tokens":10}}}'),
            _sse("content_block_start", '{"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}'),
            _sse("content_block_delta", '{"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello "}}'),
            _sse("content_block_delta", '{"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"world"}}'),
            _sse("content_block_stop", '{"type":"content_block_stop","index":0}'),
            _sse("message_delta", '{"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}'),
            _sse("message_stop", '{"type":"message_stop"}'),
        ]
        _install_fake_stream(adapter, sse)

        chunks = []
        async for ch in adapter.chat_stream(
            [Message(role=MessageRole.USER, content="hi")]
        ):
            chunks.append(ch)

        text = "".join(c.content for c in chunks)
        assert "Hello world" in text
        assert all(c.tool_calls is None for c in chunks)


class TestAnthropicStreamingToolUse:
    @pytest.mark.asyncio
    async def test_text_then_tool_use(self, adapter):
        sse = [
            _sse("message_start", '{"type":"message_start","message":{"model":"claude","usage":{"input_tokens":10}}}'),
            # text block (index 0)
            _sse("content_block_start", '{"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}'),
            _sse("content_block_delta", '{"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"reading the file"}}'),
            _sse("content_block_stop", '{"type":"content_block_stop","index":0}'),
            # tool_use block (index 1)
            _sse("content_block_start", '{"type":"content_block_start","index":1,"content_block":{"type":"tool_use","id":"toolu_1","name":"ReadFile","input":{}}}'),
            _sse("content_block_delta", '{"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{\\"path\\":"}}'),
            _sse("content_block_delta", '{"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":" \\"a.txt\\"}"}}'),
            _sse("content_block_stop", '{"type":"content_block_stop","index":1}'),
            _sse("message_delta", '{"type":"message_delta","delta":{"stop_reason":"tool_use"},"usage":{"output_tokens":12}}'),
            _sse("message_stop", '{"type":"message_stop"}'),
        ]
        _install_fake_stream(adapter, sse)

        chunks = []
        async for ch in adapter.chat_stream(
            [Message(role=MessageRole.USER, content="please read a.txt")]
        ):
            chunks.append(ch)

        text = "".join(c.content for c in chunks)
        assert "reading the file" in text

        finals = [c for c in chunks if c.tool_calls]
        assert len(finals) == 1
        assert finals[0].finish_reason == "tool_use"
        tc = finals[0].tool_calls[0]
        assert tc.id == "toolu_1"
        assert tc.name == "ReadFile"
        assert tc.input == {"path": "a.txt"}
        assert tc.parse_error is None

    @pytest.mark.asyncio
    async def test_two_tool_use_blocks(self, adapter):
        sse = [
            _sse("message_start", '{"type":"message_start","message":{"model":"claude","usage":{"input_tokens":10}}}'),
            _sse("content_block_start", '{"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"a","name":"Glob"}}'),
            _sse("content_block_delta", '{"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"pattern\\":\\"*.py\\"}"}}'),
            _sse("content_block_stop", '{"type":"content_block_stop","index":0}'),
            _sse("content_block_start", '{"type":"content_block_start","index":1,"content_block":{"type":"tool_use","id":"b","name":"Bash"}}'),
            _sse("content_block_delta", '{"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{\\"command\\":\\"ls\\"}"}}'),
            _sse("content_block_stop", '{"type":"content_block_stop","index":1}'),
            _sse("message_delta", '{"type":"message_delta","delta":{"stop_reason":"tool_use"},"usage":{"output_tokens":20}}'),
            _sse("message_stop", '{"type":"message_stop"}'),
        ]
        _install_fake_stream(adapter, sse)

        chunks = []
        async for ch in adapter.chat_stream(
            [Message(role=MessageRole.USER, content="x")]
        ):
            chunks.append(ch)

        finals = [c for c in chunks if c.tool_calls]
        assert len(finals) == 1
        names = [tc.name for tc in finals[0].tool_calls]
        assert names == ["Glob", "Bash"]
        inputs = [tc.input for tc in finals[0].tool_calls]
        assert inputs == [{"pattern": "*.py"}, {"command": "ls"}]

    @pytest.mark.asyncio
    async def test_bad_partial_json_yields_parse_error(self, adapter):
        sse = [
            _sse("message_start", '{"type":"message_start","message":{"model":"claude","usage":{"input_tokens":10}}}'),
            _sse("content_block_start", '{"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"x","name":"Bash"}}'),
            _sse("content_block_delta", '{"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{not"}}'),
            _sse("content_block_stop", '{"type":"content_block_stop","index":0}'),
            _sse("message_delta", '{"type":"message_delta","delta":{"stop_reason":"tool_use"},"usage":{"output_tokens":3}}'),
            _sse("message_stop", '{"type":"message_stop"}'),
        ]
        _install_fake_stream(adapter, sse)

        chunks = []
        async for ch in adapter.chat_stream(
            [Message(role=MessageRole.USER, content="x")]
        ):
            chunks.append(ch)

        finals = [c for c in chunks if c.tool_calls]
        assert len(finals) == 1
        tc = finals[0].tool_calls[0]
        assert tc.parse_error is not None
        assert tc.input == {}


class TestAnthropicRequestPayload:
    @pytest.mark.asyncio
    async def test_tools_propagated(self, adapter):
        sse = [
            _sse("message_start", '{"type":"message_start","message":{"model":"claude","usage":{"input_tokens":10}}}'),
            _sse("message_delta", '{"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":1}}'),
            _sse("message_stop", '{"type":"message_stop"}'),
        ]
        captured: dict = {}
        _install_fake_stream(adapter, sse, captured=captured)
        tools = [{"name": "ReadFile", "description": "...", "input_schema": {"type": "object"}}]
        async for _ in adapter.chat_stream(
            [Message(role=MessageRole.USER, content="x")], tools=tools
        ):
            pass
        payload = captured["payload"]
        assert payload["tools"][0]["name"] == "ReadFile"
        assert payload["stream"] is True

    @pytest.mark.asyncio
    async def test_system_prompt_extracted_to_top_level(self, adapter):
        sse = [
            _sse("message_start", '{"type":"message_start","message":{"model":"claude","usage":{"input_tokens":1}}}'),
            _sse("message_delta", '{"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":1}}'),
            _sse("message_stop", '{"type":"message_stop"}'),
        ]
        captured: dict = {}
        _install_fake_stream(adapter, sse, captured=captured)
        async for _ in adapter.chat_stream([
            Message(role=MessageRole.SYSTEM, content="you are helpful"),
            Message(role=MessageRole.USER, content="hi"),
        ]):
            pass
        payload = captured["payload"]
        assert payload["system"] == "you are helpful"
        # system shouldn't appear inside the messages array
        assert all(m["role"] != "system" for m in payload["messages"])
