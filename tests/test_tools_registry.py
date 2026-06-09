"""Tests for ToolRegistry."""

from pathlib import Path

import pytest

from mewcode.engine.tools.base import Tool, ToolContext, ToolError, ToolResult
from mewcode.engine.tools.registry import ToolRegistry


class _Echo(Tool):
    name = "echo"
    description = "echo input"
    input_schema = {"type": "object", "properties": {"msg": {"type": "string"}}}
    category = "search"
    is_read_only = True
    is_concurrency_safe = True

    async def execute(self, ctx, input):
        return ToolResult(content=str(input.get("msg", "")))


class _Boom(Tool):
    name = "boom"
    description = "raises"
    input_schema = {"type": "object"}
    category = "shell"
    is_read_only = False

    async def execute(self, ctx, input):
        raise RuntimeError("kaboom")


class _SystemBoom(Tool):
    name = "sysboom"
    description = "system error"
    input_schema = {"type": "object"}
    category = "shell"
    is_read_only = False

    async def execute(self, ctx, input):
        raise ToolError("system level")


class _BadInput(Tool):
    name = "badinput"
    description = "rejects all"
    input_schema = {"type": "object"}
    category = "shell"
    is_read_only = False

    def validate_input(self, input):
        return "always invalid"

    async def execute(self, ctx, input):
        return ToolResult(content="unreachable")


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext.detect(working_dir=tmp_path)


@pytest.fixture
def reg(ctx: ToolContext) -> ToolRegistry:
    r = ToolRegistry(ctx)
    r.register(_Echo())
    r.register(_Boom())
    r.register(_SystemBoom())
    r.register(_BadInput())
    return r


class TestRegistration:
    def test_duplicate_raises(self, reg):
        with pytest.raises(ValueError):
            reg.register(_Echo())

    def test_empty_name_raises(self, reg):
        class _Anon(_Echo):
            name = ""

        with pytest.raises(ValueError):
            reg.register(_Anon())


class TestEnableSpec:
    def test_enable_all(self, reg):
        reg.enable("all")
        names = {t.name for t in reg.list_enabled()}
        assert names == {"echo", "boom", "sysboom", "badinput"}

    def test_enable_readonly(self, reg):
        reg.enable("readonly")
        names = {t.name for t in reg.list_enabled()}
        assert names == {"echo"}

    def test_enable_list(self, reg):
        reg.enable(["echo", "boom", "unknown"])
        names = {t.name for t in reg.list_enabled()}
        assert names == {"echo", "boom"}

    def test_enable_unknown_spec(self, reg):
        with pytest.raises(ValueError):
            reg.enable("garbage")


class TestProtocolFormats:
    def test_openai_format_shape(self, reg):
        reg.enable(["echo"])
        out = reg.to_openai_format()
        assert len(out) == 1
        item = out[0]
        assert item["type"] == "function"
        assert item["function"]["name"] == "echo"
        assert item["function"]["description"] == "echo input"
        assert item["function"]["parameters"]["type"] == "object"

    def test_anthropic_format_shape(self, reg):
        reg.enable(["echo"])
        out = reg.to_anthropic_format()
        assert len(out) == 1
        item = out[0]
        assert item["name"] == "echo"
        assert item["description"] == "echo input"
        assert item["input_schema"]["type"] == "object"


class TestExecuteDispatch:
    @pytest.mark.asyncio
    async def test_unknown_tool(self, reg):
        r = await reg.execute("nope", {})
        assert r.is_error
        assert "not registered" in r.content

    @pytest.mark.asyncio
    async def test_disabled_tool(self, reg):
        reg.enable(["boom"])
        r = await reg.execute("echo", {})
        assert r.is_error
        assert "not registered" in r.content or "disabled" in r.content

    @pytest.mark.asyncio
    async def test_validate_input_failure(self, reg):
        r = await reg.execute("badinput", {})
        assert r.is_error
        assert "Invalid input" in r.content
        assert "always invalid" in r.content

    @pytest.mark.asyncio
    async def test_execution_exception_wrapped(self, reg):
        r = await reg.execute("boom", {})
        assert r.is_error
        assert "kaboom" in r.content
        # not propagated

    @pytest.mark.asyncio
    async def test_system_error_propagates(self, reg):
        with pytest.raises(ToolError):
            await reg.execute("sysboom", {})

    @pytest.mark.asyncio
    async def test_success_returns_result(self, reg):
        r = await reg.execute("echo", {"msg": "hello"})
        assert not r.is_error
        assert r.content == "hello"
        # registry annotates metadata
        assert r.metadata.get("tool") == "echo"
        assert "duration_ms" in r.metadata


class TestGet:
    def test_respects_enabled(self, reg):
        reg.enable(["echo"])
        assert reg.get("echo") is not None
        assert reg.get("boom") is None
