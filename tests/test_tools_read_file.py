"""Tests for ReadFileTool."""

from pathlib import Path

import pytest

from mewcode.engine.tools.base import ToolContext
from mewcode.engine.tools.read_file import ReadFileTool


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext.detect(working_dir=tmp_path)


@pytest.fixture
def tool() -> ReadFileTool:
    return ReadFileTool()


class TestReadFileSuccess:
    @pytest.mark.asyncio
    async def test_returns_line_numbered_content(self, tool, ctx, tmp_path):
        p = tmp_path / "a.txt"
        p.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
        r = await tool.execute(ctx, {"path": "a.txt"})
        assert not r.is_error
        assert r.content.startswith("1\talpha\n2\tbeta\n3\tgamma")

    @pytest.mark.asyncio
    async def test_offset_and_limit(self, tool, ctx, tmp_path):
        p = tmp_path / "b.txt"
        p.write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
        r = await tool.execute(ctx, {"path": "b.txt", "offset": 2, "limit": 2})
        assert not r.is_error
        assert r.content.startswith("2\tb\n3\tc")
        assert "more lines" in r.content  # truncation suffix

    @pytest.mark.asyncio
    async def test_empty_file(self, tool, ctx, tmp_path):
        p = tmp_path / "e.txt"
        p.write_text("", encoding="utf-8")
        r = await tool.execute(ctx, {"path": "e.txt"})
        assert not r.is_error
        assert "(empty file)" in r.content

    @pytest.mark.asyncio
    async def test_absolute_path(self, tool, ctx, tmp_path):
        p = tmp_path / "abs.txt"
        p.write_text("x\n", encoding="utf-8")
        r = await tool.execute(ctx, {"path": str(p)})
        assert not r.is_error


class TestReadFileErrors:
    @pytest.mark.asyncio
    async def test_missing_file(self, tool, ctx):
        r = await tool.execute(ctx, {"path": "nope.txt"})
        assert r.is_error
        assert "not found" in r.content.lower()

    @pytest.mark.asyncio
    async def test_directory_path(self, tool, ctx, tmp_path):
        d = tmp_path / "dir"
        d.mkdir()
        r = await tool.execute(ctx, {"path": "dir"})
        assert r.is_error
        assert "not a regular file" in r.content.lower()

    @pytest.mark.asyncio
    async def test_binary_file(self, tool, ctx, tmp_path):
        p = tmp_path / "bin.dat"
        p.write_bytes(b"AAA\x00BBB" + b"C" * 200)
        r = await tool.execute(ctx, {"path": "bin.dat"})
        assert r.is_error
        assert "binary" in r.content.lower()

    @pytest.mark.asyncio
    async def test_offset_past_end(self, tool, ctx, tmp_path):
        p = tmp_path / "small.txt"
        p.write_text("only\nthree\nlines\n", encoding="utf-8")
        r = await tool.execute(ctx, {"path": "small.txt", "offset": 99})
        assert r.is_error
        assert "past end" in r.content.lower()


class TestReadFileValidation:
    def test_path_required(self, tool):
        assert tool.validate_input({"path": ""})
        assert tool.validate_input({})

    def test_offset_must_be_positive(self, tool):
        assert tool.validate_input({"path": "x", "offset": 0})
        assert tool.validate_input({"path": "x", "offset": -1})

    def test_limit_must_be_positive(self, tool):
        assert tool.validate_input({"path": "x", "limit": 0})

    def test_valid_input(self, tool):
        assert tool.validate_input({"path": "x"}) is None
        assert tool.validate_input({"path": "x", "offset": 1, "limit": 10}) is None
