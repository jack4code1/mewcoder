"""Tests for GlobTool."""

import time
from pathlib import Path

import pytest

from mewcode.engine.tools.base import ToolContext
from mewcode.engine.tools.glob import GlobTool


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext.detect(working_dir=tmp_path)


@pytest.fixture
def tool() -> GlobTool:
    return GlobTool()


class TestGlobSuccess:
    @pytest.mark.asyncio
    async def test_recursive_pattern(self, tool, ctx, tmp_path):
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.py").write_text("b")
        sub = tmp_path / "sub" / "deep"
        sub.mkdir(parents=True)
        (sub / "c.py").write_text("c")

        r = await tool.execute(ctx, {"pattern": "**/*.py"})
        assert not r.is_error
        names = {line.rsplit("/", 1)[-1] for line in r.content.splitlines() if line}
        assert {"a.py", "b.py", "c.py"} <= names

    @pytest.mark.asyncio
    async def test_top_level_pattern(self, tool, ctx, tmp_path):
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.py").write_text("b")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "c.py").write_text("c")

        r = await tool.execute(ctx, {"pattern": "*.py"})
        names = set(r.content.splitlines())
        assert names == {"a.py", "b.py"}

    @pytest.mark.asyncio
    async def test_excludes_noisy_dirs(self, tool, ctx, tmp_path):
        for noisy in (".git", "node_modules", "__pycache__", ".venv"):
            d = tmp_path / noisy
            d.mkdir(parents=True)
            (d / "evil.py").write_text("e")
        # legit file
        (tmp_path / "ok.py").write_text("ok")

        r = await tool.execute(ctx, {"pattern": "**/*.py"})
        assert not r.is_error
        for noisy in (".git", "node_modules", "__pycache__", ".venv"):
            assert noisy not in r.content
        assert "ok.py" in r.content

    @pytest.mark.asyncio
    async def test_mtime_descending(self, tool, ctx, tmp_path):
        old = tmp_path / "old.py"
        new = tmp_path / "new.py"
        old.write_text("o")
        time.sleep(0.05)
        new.write_text("n")

        r = await tool.execute(ctx, {"pattern": "*.py"})
        lines = [l for l in r.content.splitlines() if l]
        assert lines[0] == "new.py"
        assert lines[-1] == "old.py"

    @pytest.mark.asyncio
    async def test_no_matches(self, tool, ctx, tmp_path):
        r = await tool.execute(ctx, {"pattern": "*.no_such_ext"})
        assert "no files matched" in r.content


class TestGlobCap:
    @pytest.mark.asyncio
    async def test_cap_at_200(self, tool, ctx, tmp_path):
        big = tmp_path / "many"
        big.mkdir()
        for i in range(205):
            (big / f"f{i:04d}.txt").write_text("x")

        r = await tool.execute(ctx, {"pattern": "many/*.txt"})
        assert not r.is_error
        assert r.metadata["match_count"] == 205
        assert r.metadata["returned"] == 200
        assert r.metadata["truncated"] is True
        assert "more matches omitted" in r.content


class TestGlobErrors:
    @pytest.mark.asyncio
    async def test_invalid_root(self, tool, ctx):
        r = await tool.execute(ctx, {"pattern": "*", "path": "no/such/root"})
        assert r.is_error


class TestGlobValidation:
    def test_pattern_required(self, tool):
        assert tool.validate_input({"pattern": ""})

    def test_path_must_be_string(self, tool):
        assert tool.validate_input({"pattern": "*", "path": ""})

    def test_valid(self, tool):
        assert tool.validate_input({"pattern": "*"}) is None
