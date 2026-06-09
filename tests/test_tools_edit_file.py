"""Tests for EditFileTool."""

from pathlib import Path

import pytest

from mewcode.engine.tools.base import ToolContext
from mewcode.engine.tools.edit_file import EditFileTool


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext.detect(working_dir=tmp_path)


@pytest.fixture
def tool() -> EditFileTool:
    return EditFileTool()


class TestEditFileSuccess:
    @pytest.mark.asyncio
    async def test_unique_replace(self, tool, ctx, tmp_path):
        p = tmp_path / "s.py"
        p.write_text("def main():\n    print('hello')\n    return 0\n", encoding="utf-8")
        r = await tool.execute(ctx, {
            "path": "s.py",
            "old_string": "print('hello')",
            "new_string": "print('world')",
        })
        assert not r.is_error
        assert "Preview" in r.content
        assert "world" in p.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_empty_new_string_deletes(self, tool, ctx, tmp_path):
        p = tmp_path / "s.py"
        p.write_text("keep1\nDELETE_ME\nkeep2\n", encoding="utf-8")
        r = await tool.execute(ctx, {
            "path": "s.py",
            "old_string": "DELETE_ME\n",
            "new_string": "",
        })
        assert not r.is_error
        assert p.read_text(encoding="utf-8") == "keep1\nkeep2\n"

    @pytest.mark.asyncio
    async def test_preview_shows_change_area(self, tool, ctx, tmp_path):
        p = tmp_path / "s.py"
        p.write_text("L1\nL2\nTARGET\nL4\nL5\n", encoding="utf-8")
        r = await tool.execute(ctx, {
            "path": "s.py",
            "old_string": "TARGET",
            "new_string": "REPLACED",
        })
        assert not r.is_error
        # context lines around the change
        assert "REPLACED" in r.content
        assert "L1" in r.content
        assert "L5" in r.content


class TestEditFileErrors:
    @pytest.mark.asyncio
    async def test_zero_matches(self, tool, ctx, tmp_path):
        p = tmp_path / "s.py"
        p.write_text("hello\n", encoding="utf-8")
        r = await tool.execute(ctx, {
            "path": "s.py",
            "old_string": "NOT_THERE",
            "new_string": "X",
        })
        assert r.is_error
        assert "not found" in r.content.lower()
        assert "stale" in r.content.lower()

    @pytest.mark.asyncio
    async def test_multiple_matches(self, tool, ctx, tmp_path):
        p = tmp_path / "s.py"
        p.write_text("foo\nfoo\nbar\n", encoding="utf-8")
        r = await tool.execute(ctx, {
            "path": "s.py",
            "old_string": "foo",
            "new_string": "baz",
        })
        assert r.is_error
        assert "appears 2 times" in r.content
        assert r.metadata["match_count"] == 2

    @pytest.mark.asyncio
    async def test_missing_file(self, tool, ctx):
        r = await tool.execute(ctx, {
            "path": "nope.py",
            "old_string": "x",
            "new_string": "y",
        })
        assert r.is_error
        assert "not found" in r.content.lower()


class TestEditFileValidation:
    def test_old_string_required(self, tool):
        assert tool.validate_input({"path": "p", "old_string": "", "new_string": "x"})

    def test_new_string_must_be_string(self, tool):
        assert tool.validate_input({"path": "p", "old_string": "x", "new_string": None})

    def test_identical_rejected(self, tool):
        assert tool.validate_input({"path": "p", "old_string": "x", "new_string": "x"})

    def test_valid(self, tool):
        assert tool.validate_input({"path": "p", "old_string": "a", "new_string": ""}) is None
