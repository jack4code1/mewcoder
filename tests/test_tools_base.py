"""Tests for the tool subsystem core types: Tool, ToolResult, ToolContext, ToolError."""

from pathlib import Path

import pytest

from mewcode.engine.tools.base import Tool, ToolContext, ToolError, ToolResult


class TestToolResult:
    def test_defaults(self):
        r = ToolResult(content="ok")
        assert r.content == "ok"
        assert r.is_error is False
        assert r.metadata == {}

    def test_error_result(self):
        r = ToolResult(content="bad", is_error=True, metadata={"reason": "x"})
        assert r.is_error is True
        assert r.metadata["reason"] == "x"


class TestToolContext:
    def test_resolve_absolute(self, tmp_path: Path):
        ctx = ToolContext.detect(working_dir=tmp_path)
        target = tmp_path / "abs.txt"
        # absolute paths are kept as-is (after .resolve())
        resolved = ctx.resolve_path(str(target))
        assert resolved == target.resolve()

    def test_resolve_relative_uses_working_dir(self, tmp_path: Path):
        ctx = ToolContext.detect(working_dir=tmp_path)
        resolved = ctx.resolve_path("sub/inner.txt")
        # parent must be the working_dir's resolve
        assert resolved == (tmp_path / "sub" / "inner.txt").resolve()

    def test_resolve_nonexistent_does_not_raise(self, tmp_path: Path):
        ctx = ToolContext.detect(working_dir=tmp_path)
        resolved = ctx.resolve_path("does/not/exist.txt")
        # Should still produce an absolute path
        assert resolved.is_absolute()

    def test_detect_populates_os_and_shell(self):
        ctx = ToolContext.detect()
        assert ctx.os_name in ("windows", "darwin", "linux")
        assert ctx.platform_shell in ("cmd", "sh")
        assert ctx.working_dir.exists()


class _NoopTool(Tool):
    name = "Noop"
    description = "noop"
    input_schema = {"type": "object", "properties": {}}
    category = "search"
    is_read_only = True
    is_concurrency_safe = True

    async def execute(self, ctx, input):
        return ToolResult(content="noop")


class TestToolBase:
    def test_subclass_can_be_instantiated(self):
        t = _NoopTool()
        assert t.name == "Noop"
        assert t.is_read_only is True

    def test_default_validate_returns_none(self):
        t = _NoopTool()
        assert t.validate_input({}) is None

    @pytest.mark.asyncio
    async def test_execute_returns_tool_result(self, tmp_path: Path):
        t = _NoopTool()
        ctx = ToolContext.detect(working_dir=tmp_path)
        r = await t.execute(ctx, {})
        assert isinstance(r, ToolResult)
        assert r.content == "noop"


class TestToolError:
    def test_is_exception(self):
        with pytest.raises(ToolError):
            raise ToolError("boom")
