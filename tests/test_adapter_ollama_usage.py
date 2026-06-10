from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Iterable

import pytest

from mewcode.engine.adapters.ollama_adapter import OllamaAdapter
from mewcode.engine.models import Message, MessageRole, TokenUsage


class _FakeStreamResponse:
    def __init__(self, chunks: Iterable[bytes]):
        self._chunks = list(chunks)

    def raise_for_status(self) -> None:
        return None

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


def _install_fake_stream(adapter, chunks: list[bytes], captured: dict | None = None):
    @asynccontextmanager
    async def fake_stream(method, url, json=None):
        if captured is not None:
            captured["payload"] = json
            captured["url"] = url
        yield _FakeStreamResponse(chunks)

    adapter.client.stream = fake_stream  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_ollama_streaming_final_usage_maps_to_token_usage():
    adapter = OllamaAdapter(model="llama3", base_url="http://example.test")
    chunks = [
        b'{"model":"llama3","message":{"content":"Hello"},"done":false}\n',
        (
            b'{"model":"llama3","message":{"content":""},"done":true,'
            b'"prompt_eval_count":10,"eval_count":20}\n'
        ),
    ]
    _install_fake_stream(adapter, chunks)

    results = []
    async for chunk in adapter.chat_stream(
        [Message(role=MessageRole.USER, content="hi")]
    ):
        results.append(chunk)

    usage_chunks = [chunk for chunk in results if chunk.token_usage is not None]

    assert [chunk.token_usage for chunk in usage_chunks] == [
        TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    ]
