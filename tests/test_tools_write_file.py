"""Tests for WriteFileTool."""

from pathlib import Path

import pytest

from mewcode.engine.tools.base import ToolContext
from mewcode.engine.tools.write_file import WriteFileTool


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext.detect(working_dir=tmp_path)


@pytest.fixture
def tool() -> WriteFileTool:
    return WriteFileTool()


class TestWriteFileSuccess:
    @pytest.mark.asyncio
    async def test_creates_parent_directories(self, tool, ctx, tmp_path):
        r = await tool.execute(ctx, {"path": "a/b/c/d.txt", "content": "hi"})
        assert not r.is_error
        target = tmp_path / "a" / "b" / "c" / "d.txt"
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "hi"

    @pytest.mark.asyncio
    async def test_overwrites_existing(self, tool, ctx, tmp_path):
        target = tmp_path / "f.txt"
        target.write_text("old", encoding="utf-8")
        r = await tool.execute(ctx, {"path": "f.txt", "content": "new"})
        assert not r.is_error
        assert target.read_text(encoding="utf-8") == "new"

    @pytest.mark.asyncio
    async def test_unicode_content(self, tool, ctx, tmp_path):
        target = tmp_path / "u.txt"
        await tool.execute(ctx, {"path": "u.txt", "content": "你好 🐱"})
        assert target.read_text(encoding="utf-8") == "你好 🐱"

    @pytest.mark.asyncio
    async def test_absolute_path(self, tool, ctx, tmp_path):
        target = tmp_path / "abs.txt"
        r = await tool.execute(ctx, {"path": str(target), "content": "x"})
        assert not r.is_error
        assert target.read_text(encoding="utf-8") == "x"


class TestWriteFileErrors:
    @pytest.mark.asyncio
    async def test_path_is_directory(self, tool, ctx, tmp_path):
        d = tmp_path / "somedir"
        d.mkdir()
        r = await tool.execute(ctx, {"path": "somedir", "content": "x"})
        assert r.is_error
        assert "directory" in r.content.lower()


class TestWriteFileValidation:
    def test_path_required(self, tool):
        assert tool.validate_input({"path": "", "content": "x"})

    def test_content_required(self, tool):
        assert tool.validate_input({"path": "p"})

    def test_valid(self, tool):
        assert tool.validate_input({"path": "p", "content": "c"}) is None
