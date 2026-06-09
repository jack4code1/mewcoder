"""Tests for OpenAI-protocol tool_calls streaming aggregation.

Covers CustomAdapter (the default protocol used by mimo-v2.5-pro) and
OpenAIAdapter. We feed pre-canned SSE byte streams through a fake
httpx.AsyncClient.stream context manager and assert that the adapter
yields the right sequence of StreamChunk objects, including a final
chunk carrying the aggregated tool_calls.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Iterable

import pytest

from mewcode.engine.adapters.custom_adapter import CustomAdapter
from mewcode.engine.adapters.openai_adapter import OpenAIAdapter
from mewcode.engine.adapters._openai_protocol import OpenAIToolCallAggregator
from mewcode.engine.models import Message, MessageRole


# ----- helpers --------------------------------------------------------------


class _FakeStreamResponse:
    def __init__(self, chunks: Iterable[bytes]):
        self._chunks = list(chunks)

    def raise_for_status(self) -> None:
        return None

    async def aiter_bytes(self):
        for c in self._chunks:
            yield c


def _install_fake_stream(adapter, sse_chunks: list[bytes], captured: dict | None = None):
    """Patch the adapter's httpx client so .stream() yields our pre-canned bytes.

    If ``captured`` is provided, the request payload is stored under the key
    ``"payload"`` for assertions.
    """

    @asynccontextmanager
    async def fake_stream(method, url, json=None):
        if captured is not None:
            captured["payload"] = json
            captured["url"] = url
            captured["method"] = method
        yield _FakeStreamResponse(sse_chunks)

    adapter.client.stream = fake_stream  # type: ignore[assignment]


def _sse(line: str) -> bytes:
    return f"data: {line}\n".encode("utf-8")


# ----- aggregator-only tests (no adapter wiring) ---------------------------


class TestAggregator:
    def test_two_calls_two_indices(self):
        agg = OpenAIToolCallAggregator()
        agg.feed([{"index": 0, "id": "a", "function": {"name": "ReadFile"}}])
        agg.feed([{"index": 0, "function": {"arguments": '{"path"'}}])
        agg.feed([{"index": 0, "function": {"arguments": ': "x"}'}}])
        agg.feed([{"index": 1, "id": "b", "function": {"name": "Bash"}}])
        agg.feed([{"index": 1, "function": {"arguments": '{"command":"ls"}'}}])
        calls = agg.finalize()
        assert [c.id for c in calls] == ["a", "b"]
        assert [c.name for c in calls] == ["ReadFile", "Bash"]
        assert calls[0].input == {"path": "x"}
        assert calls[1].input == {"command": "ls"}

    def test_bad_json_sets_parse_error(self):
        agg = OpenAIToolCallAggregator()
        agg.feed([{"index": 0, "id": "x", "function": {"name": "Bash", "arguments": "{not"}}])
        calls = agg.finalize()
        assert len(calls) == 1
        assert calls[0].parse_error and "parse" in calls[0].parse_error.lower()
        assert calls[0].input == {}

    def test_empty_arguments_treated_as_empty_object(self):
        agg = OpenAIToolCallAggregator()
        agg.feed([{"index": 0, "id": "x", "function": {"name": "Glob"}}])
        calls = agg.finalize()
        assert calls[0].input == {}
        assert calls[0].parse_error is None

    def test_non_object_args_rejected(self):
        agg = OpenAIToolCallAggregator()
        agg.feed([{"index": 0, "id": "x", "function": {"name": "Bash", "arguments": '"a string"'}}])
        calls = agg.finalize()
        assert calls[0].parse_error and "object" in calls[0].parse_error.lower()

    def test_no_calls(self):
        agg = OpenAIToolCallAggregator()
        assert not agg.has_calls()
        assert agg.finalize() == []


# ----- adapter streaming tests ---------------------------------------------


def _adapter_custom() -> CustomAdapter:
    return CustomAdapter(
        model="mimo-v2.5-pro",
        api_key="dummy",
        base_url="https://example.test/v1",
    )


def _adapter_openai() -> OpenAIAdapter:
    return OpenAIAdapter(
        model="gpt-4o-mini",
        api_key="dummy",
        base_url="https://example.test/v1",
    )


@pytest.mark.parametrize(
    "adapter_factory",
    [_adapter_custom, _adapter_openai],
    ids=["custom", "openai"],
)
class TestOpenAIStreamingToolCalls:
    @pytest.mark.asyncio
    async def test_text_only_no_tool_calls(self, adapter_factory):
        adapter = adapter_factory()
        sse = [
            _sse('{"choices":[{"delta":{"content":"Hello"}}]}'),
            _sse('{"choices":[{"delta":{"content":" world"}}]}'),
            _sse('{"choices":[{"delta":{},"finish_reason":"stop"}]}'),
            b"data: [DONE]\n",
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

    @pytest.mark.asyncio
    async def test_streamed_tool_call_aggregation(self, adapter_factory):
        adapter = adapter_factory()
        sse = [
            # text first
            _sse('{"choices":[{"delta":{"content":"reading"}}]}'),
            # tool_call: id+name
            _sse('{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"ReadFile"}}]}}]}'),
            # arguments fragments
            _sse('{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"path\\":"}}]}}]}'),
            _sse('{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":" \\"a.txt\\"}"}}]}}]}'),
            # finish
            _sse('{"choices":[{"delta":{},"finish_reason":"tool_calls"}]}'),
            b"data: [DONE]\n",
        ]
        _install_fake_stream(adapter, sse)

        chunks = []
        async for ch in adapter.chat_stream(
            [Message(role=MessageRole.USER, content="please read a.txt")]
        ):
            chunks.append(ch)

        text = "".join(c.content for c in chunks)
        assert "reading" in text

        finals = [c for c in chunks if c.tool_calls]
        assert len(finals) == 1
        tc = finals[0].tool_calls[0]
        assert tc.id == "call_1"
        assert tc.name == "ReadFile"
        assert tc.input == {"path": "a.txt"}
        assert tc.parse_error is None

    @pytest.mark.asyncio
    async def test_two_concurrent_tool_calls(self, adapter_factory):
        adapter = adapter_factory()
        sse = [
            _sse('{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"a","function":{"name":"ReadFile"}}]}}]}'),
            _sse('{"choices":[{"delta":{"tool_calls":[{"index":1,"id":"b","function":{"name":"Glob"}}]}}]}'),
            _sse('{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"path\\":\\"x\\"}"}}]}}]}'),
            _sse('{"choices":[{"delta":{"tool_calls":[{"index":1,"function":{"arguments":"{\\"pattern\\":\\"*.py\\"}"}}]}}]}'),
            _sse('{"choices":[{"delta":{},"finish_reason":"tool_calls"}]}'),
            b"data: [DONE]\n",
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
        assert names == ["ReadFile", "Glob"]
        inputs = [tc.input for tc in finals[0].tool_calls]
        assert inputs == [{"path": "x"}, {"pattern": "*.py"}]

    @pytest.mark.asyncio
    async def test_bad_arguments_json_does_not_crash(self, adapter_factory):
        adapter = adapter_factory()
        sse = [
            _sse('{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_x","function":{"name":"Bash","arguments":"{not json"}}]}}]}'),
            _sse('{"choices":[{"delta":{},"finish_reason":"tool_calls"}]}'),
            b"data: [DONE]\n",
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

    @pytest.mark.asyncio
    async def test_tools_param_propagated_to_request(self, adapter_factory):
        adapter = adapter_factory()
        sse = [
            _sse('{"choices":[{"delta":{"content":"ok"}}]}'),
            _sse('{"choices":[{"delta":{},"finish_reason":"stop"}]}'),
            b"data: [DONE]\n",
        ]
        captured: dict = {}
        _install_fake_stream(adapter, sse, captured=captured)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "ReadFile",
                    "description": "...",
                    "parameters": {"type": "object"},
                },
            }
        ]
        async for _ in adapter.chat_stream(
            [Message(role=MessageRole.USER, content="x")], tools=tools
        ):
            pass

        payload = captured["payload"]
        assert "tools" in payload
        assert payload["tools"][0]["function"]["name"] == "ReadFile"

    @pytest.mark.asyncio
    async def test_no_tools_param_when_omitted(self, adapter_factory):
        adapter = adapter_factory()
        sse = [
            _sse('{"choices":[{"delta":{"content":"ok"}}]}'),
            _sse('{"choices":[{"delta":{},"finish_reason":"stop"}]}'),
            b"data: [DONE]\n",
        ]
        captured: dict = {}
        _install_fake_stream(adapter, sse, captured=captured)
        async for _ in adapter.chat_stream(
            [Message(role=MessageRole.USER, content="x")]
        ):
            pass
        assert "tools" not in captured["payload"]
