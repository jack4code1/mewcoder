"""Tests for GrepTool."""

from pathlib import Path

import pytest

from mewcode.engine.tools.base import ToolContext
from mewcode.engine.tools.grep import GrepTool


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext.detect(working_dir=tmp_path)


@pytest.fixture
def tool() -> GrepTool:
    return GrepTool()


class TestGrepSuccess:
    @pytest.mark.asyncio
    async def test_basic_regex(self, tool, ctx, tmp_path):
        (tmp_path / "a.py").write_text(
            "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
        )
        r = await tool.execute(ctx, {"pattern": r"def\s+\w+"})
        assert not r.is_error
        assert "a.py:1: def foo" in r.content
        assert "a.py:4: def bar" in r.content

    @pytest.mark.asyncio
    async def test_include_filter(self, tool, ctx, tmp_path):
        (tmp_path / "a.py").write_text("hit\n")
        (tmp_path / "b.txt").write_text("hit\n")
        r = await tool.execute(ctx, {"pattern": "hit", "include": "*.py"})
        assert "a.py:" in r.content
        assert "b.txt" not in r.content

    @pytest.mark.asyncio
    async def test_context_lines(self, tool, ctx, tmp_path):
        (tmp_path / "f.py").write_text("L1\nL2\nMATCH\nL4\nL5\n")
        r = await tool.execute(ctx, {"pattern": "MATCH", "context": 1})
        assert "f.py:2:" in r.content   # context-before
        assert "f.py:3:" in r.content   # match
        assert "f.py:4:" in r.content   # context-after

    @pytest.mark.asyncio
    async def test_excludes_binary(self, tool, ctx, tmp_path):
        (tmp_path / "binary.dat").write_bytes(b"\x00binary\x00data")
        (tmp_path / "text.txt").write_text("binary text\n")
        r = await tool.execute(ctx, {"pattern": "binary"})
        assert "binary.dat" not in r.content
        assert "text.txt:1:" in r.content

    @pytest.mark.asyncio
    async def test_excludes_noisy_dirs(self, tool, ctx, tmp_path):
        for noisy in (".git", "node_modules", ".venv"):
            d = tmp_path / noisy
            d.mkdir()
            (d / "f.py").write_text("hit\n")
        (tmp_path / "ok.py").write_text("hit\n")

        r = await tool.execute(ctx, {"pattern": "hit"})
        assert "ok.py:" in r.content
        for noisy in (".git", "node_modules", ".venv"):
            assert noisy not in r.content


class TestGrepCap:
    @pytest.mark.asyncio
    async def test_cap_at_100(self, tool, ctx, tmp_path):
        (tmp_path / "big.txt").write_text("hit\n" * 150)
        r = await tool.execute(ctx, {"pattern": "hit"})
        assert r.metadata["match_count"] == 100
        assert r.metadata["truncated"] is True
        assert "match cap" in r.content


class TestGrepErrors:
    @pytest.mark.asyncio
    async def test_invalid_path(self, tool, ctx):
        r = await tool.execute(ctx, {"pattern": "x", "path": "no/such"})
        assert r.is_error


class TestGrepValidation:
    def test_pattern_required(self, tool):
        assert tool.validate_input({"pattern": ""})

    def test_invalid_regex(self, tool):
        err = tool.validate_input({"pattern": "["})
        assert err and "invalid regex" in err.lower()

    def test_context_range(self, tool):
        assert tool.validate_input({"pattern": "x", "context": -1})
        assert tool.validate_input({"pattern": "x", "context": 99})

    def test_valid(self, tool):
        assert tool.validate_input({"pattern": "x"}) is None
        assert tool.validate_input(
            {"pattern": "x", "context": 3, "include": "*.py", "path": "."}
        ) is None
