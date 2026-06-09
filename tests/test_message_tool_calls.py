"""Tests for ToolCall and Message tool-calling extensions, including
backward compatibility with legacy session YAML."""

from datetime import datetime

import pytest

from mewcode.engine.models.message import (
    Message,
    MessageRole,
    StreamChunk,
    ToolCall,
)


class TestToolCallRoundtrip:
    def test_basic(self):
        tc = ToolCall(id="c1", name="ReadFile", input={"path": "a.txt"})
        d = tc.to_dict()
        assert d == {"id": "c1", "name": "ReadFile", "input": {"path": "a.txt"}}
        rt = ToolCall.from_dict(d)
        assert rt == tc

    def test_with_parse_error(self):
        tc = ToolCall(id="c2", name="Bash", input={}, parse_error="bad json")
        d = tc.to_dict()
        assert d["parse_error"] == "bad json"
        rt = ToolCall.from_dict(d)
        assert rt.parse_error == "bad json"

    def test_omits_parse_error_when_absent(self):
        tc = ToolCall(id="c3", name="Glob", input={"pattern": "*.py"})
        d = tc.to_dict()
        assert "parse_error" not in d


class TestMessageWithToolCallsRoundtrip:
    def test_assistant_with_single_tool_call(self):
        tc = ToolCall(id="c1", name="ReadFile", input={"path": "x"})
        m = Message(
            role=MessageRole.ASSISTANT,
            content="reading the file",
            tool_calls=[tc],
        )
        d = m.to_dict()
        assert "tool_calls" in d
        assert d["tool_calls"][0]["name"] == "ReadFile"

        rt = Message.from_dict(d)
        assert rt.role == MessageRole.ASSISTANT
        assert rt.content == "reading the file"
        assert rt.tool_calls is not None
        assert len(rt.tool_calls) == 1
        assert rt.tool_calls[0].id == "c1"
        assert rt.tool_calls[0].input == {"path": "x"}

    def test_assistant_with_multiple_tool_calls(self):
        tc1 = ToolCall(id="c1", name="Glob", input={"pattern": "*.py"})
        tc2 = ToolCall(id="c2", name="ReadFile", input={"path": "a.py"})
        m = Message(role=MessageRole.ASSISTANT, content="", tool_calls=[tc1, tc2])
        rt = Message.from_dict(m.to_dict())
        assert [t.name for t in rt.tool_calls] == ["Glob", "ReadFile"]

    def test_tool_role_message_roundtrip(self):
        m = Message(
            role=MessageRole.TOOL,
            content="<bash_output exit_code=0>\nhello\n</bash_output>",
            tool_call_id="c1",
            tool_result_is_error=False,
        )
        d = m.to_dict()
        assert d["tool_call_id"] == "c1"
        assert d["tool_result_is_error"] is False

        rt = Message.from_dict(d)
        assert rt.role == MessageRole.TOOL
        assert rt.tool_call_id == "c1"
        assert rt.tool_result_is_error is False

    def test_tool_result_is_error_true_preserved(self):
        m = Message(
            role=MessageRole.TOOL,
            content="File not found",
            tool_call_id="c2",
            tool_result_is_error=True,
        )
        rt = Message.from_dict(m.to_dict())
        assert rt.tool_result_is_error is True


class TestBackwardCompatibility:
    def test_legacy_message_loads_without_extensions(self):
        legacy = {
            "role": "user",
            "content": "hello",
            "timestamp": "2024-01-01T12:00:00",
        }
        m = Message.from_dict(legacy)
        assert m.role == MessageRole.USER
        assert m.content == "hello"
        assert m.tool_calls is None
        assert m.tool_call_id is None
        assert m.tool_result_is_error is None

    def test_legacy_assistant_with_metadata(self):
        legacy = {
            "role": "assistant",
            "content": "answer",
            "timestamp": "2024-01-01T12:00:00",
            "metadata": {"some_key": "value"},
        }
        m = Message.from_dict(legacy)
        assert m.metadata == {"some_key": "value"}
        assert m.tool_calls is None

    def test_to_dict_omits_empty_extensions(self):
        m = Message(role=MessageRole.USER, content="hi")
        d = m.to_dict()
        assert "tool_calls" not in d
        assert "tool_call_id" not in d
        assert "tool_result_is_error" not in d
        # original fields still present
        assert d["role"] == "user"
        assert d["content"] == "hi"

    def test_to_dict_omits_empty_metadata(self):
        m = Message(role=MessageRole.USER, content="hi")
        d = m.to_dict()
        # behaviour from chapter 01: empty metadata not emitted
        assert "metadata" not in d


class TestStreamChunkExtension:
    def test_default_no_tool_calls(self):
        ch = StreamChunk(content="x", model="m")
        assert ch.tool_calls is None

    def test_carries_tool_calls(self):
        tc = ToolCall(id="c1", name="ReadFile", input={"path": "a"})
        ch = StreamChunk(content="", model="m", tool_calls=[tc])
        assert ch.tool_calls is not None
        assert ch.tool_calls[0].name == "ReadFile"


class TestSerializationFormat:
    """Pin down the on-disk shape so future migrations notice changes."""

    def test_assistant_with_tool_calls_shape(self):
        tc = ToolCall(id="call_42", name="Bash", input={"command": "echo hi"})
        m = Message(
            role=MessageRole.ASSISTANT,
            content="running",
            timestamp=datetime.fromisoformat("2025-01-01T00:00:00"),
            tool_calls=[tc],
        )
        d = m.to_dict()
        assert d == {
            "role": "assistant",
            "content": "running",
            "timestamp": "2025-01-01T00:00:00",
            "tool_calls": [
                {"id": "call_42", "name": "Bash", "input": {"command": "echo hi"}}
            ],
        }

    def test_tool_result_shape(self):
        m = Message(
            role=MessageRole.TOOL,
            content="ok",
            timestamp=datetime.fromisoformat("2025-01-01T00:00:00"),
            tool_call_id="call_42",
            tool_result_is_error=False,
        )
        d = m.to_dict()
        assert d == {
            "role": "tool",
            "content": "ok",
            "timestamp": "2025-01-01T00:00:00",
            "tool_call_id": "call_42",
            "tool_result_is_error": False,
        }
