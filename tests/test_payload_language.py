"""Payload and model-visible language policy tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Iterable
import re

import pytest

from mewcode.engine.adapters.custom_adapter import CustomAdapter
from mewcode.engine.models import Message, MessageRole, ToolCall
from mewcode.engine.tools import ToolContext, build_default_registry, build_system_prompt


class _FakeStreamResponse:
    def __init__(self, chunks: Iterable[bytes]):
        self._chunks = list(chunks)

    def raise_for_status(self) -> None:
        return None

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


def _sse(line: str) -> bytes:
    return f"data: {line}\n".encode("utf-8")


def _install_fake_stream(adapter: CustomAdapter, captured: dict) -> None:
    sse = [
        _sse('{"choices":[{"delta":{"content":"ok"}}]}'),
        _sse('{"choices":[{"delta":{},"finish_reason":"stop"}]}'),
        b"data: [DONE]\n",
    ]

    @asynccontextmanager
    async def fake_stream(method, url, json=None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = json
        yield _FakeStreamResponse(sse)

    adapter.client.stream = fake_stream  # type: ignore[assignment]


def _adapter() -> CustomAdapter:
    return CustomAdapter(
        model="mimo-v2.5-pro",
        api_key="dummy",
        base_url="https://example.test/v1",
    )


def _ctx_and_registry():
    ctx = ToolContext(Path.cwd(), "windows", "cmd")
    return ctx, build_default_registry(ctx, {})


async def _capture_payload(messages: list[Message], tools: list[dict] | None = None) -> dict:
    adapter = _adapter()
    captured: dict = {}
    _install_fake_stream(adapter, captured)
    async for _ in adapter.chat_stream(messages, tools=tools):
        pass
    await adapter.close()
    return captured["payload"]


@pytest.mark.asyncio
async def test_payload_contains_tool_system_prompt():
    ctx, registry = _ctx_and_registry()
    system_prompt = build_system_prompt(ctx, registry)

    payload = await _capture_payload(
        [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content="read config"),
        ],
        tools=registry.to_openai_format(),
    )

    system_messages = [
        msg for msg in payload["messages"] if msg["role"] == "system"
    ]
    assert len(system_messages) == 1
    assert "Working directory:" in system_messages[0]["content"]
    assert "Host OS:" in system_messages[0]["content"]
    assert "Tool usage guidelines:" in system_messages[0]["content"]


@pytest.mark.asyncio
async def test_payload_contains_enabled_tool_descriptions():
    ctx, registry = _ctx_and_registry()

    payload = await _capture_payload(
        [Message(role=MessageRole.USER, content="read config")],
        tools=registry.to_openai_format(),
    )

    tool_names = [
        tool["function"]["name"]
        for tool in payload["tools"]
    ]
    tool_descriptions = [
        tool["function"]["description"]
        for tool in payload["tools"]
    ]
    assert tool_names == [
        "ReadFile",
        "WriteFile",
        "EditFile",
        "Bash",
        "Glob",
        "Grep",
    ]
    assert all(description for description in tool_descriptions)


@pytest.mark.asyncio
async def test_tool_metadata_is_not_serialized_to_payload():
    payload = await _capture_payload(
        [
            Message(
                role=MessageRole.ASSISTANT,
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="ReadFile",
                        input={"path": "config.yaml"},
                    )
                ],
            ),
            Message(
                role=MessageRole.TOOL,
                content="tool result",
                tool_call_id="call_1",
                metadata={"ui_only": "must-not-leak"},
            ),
        ],
    )

    serialized = str(payload["messages"])
    assert "ui_only" not in serialized
    assert "must-not-leak" not in serialized
    assert "tool result" in serialized


def test_model_visible_tool_strings_have_no_chinese_characters():
    ctx, registry = _ctx_and_registry()
    cjk = re.compile(r"[\u4e00-\u9fff]")
    visible_strings = [build_system_prompt(ctx, registry)]

    for tool in registry.list_enabled():
        visible_strings.append(tool.name)
        visible_strings.append(tool.description)
        visible_strings.append(str(tool.input_schema))

    assert not any(cjk.search(text) for text in visible_strings)
