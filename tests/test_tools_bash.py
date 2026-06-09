"""Tests for BashTool.

These tests run real subprocesses (cross-platform via the system shell).
We rely on `python` being on PATH.
"""

from pathlib import Path

import pytest

from mewcode.engine.tools.base import ToolContext
from mewcode.engine.tools.bash import BashTool


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext.detect(working_dir=tmp_path)


@pytest.fixture
def tool() -> BashTool:
    return BashTool()


class TestBashSuccess:
    @pytest.mark.asyncio
    async def test_echo_hello(self, tool, ctx):
        r = await tool.execute(ctx, {"command": "echo hello"})
        assert not r.is_error
        assert "hello" in r.content
        assert "exit_code=0" in r.content
        assert r.metadata["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_non_zero_exit_is_not_error(self, tool, ctx):
        # Use python so we don't depend on shell built-ins.
        r = await tool.execute(
            ctx, {"command": 'python -c "import sys; sys.exit(7)"'}
        )
        assert not r.is_error  # non-zero exit IS NOT a tool error
        assert "exit_code=7" in r.content
        assert r.metadata["exit_code"] == 7

    @pytest.mark.asyncio
    async def test_runs_in_working_dir(self, tool, ctx, tmp_path):
        # Create a marker file
        (tmp_path / "marker.txt").write_text("x", encoding="utf-8")
        r = await tool.execute(
            ctx, {"command": 'python -c "import os, pathlib; print(pathlib.Path(\\"marker.txt\\").exists())"'}
        )
        assert not r.is_error
        assert "True" in r.content


class TestBashTimeoutAndTruncation:
    @pytest.mark.asyncio
    async def test_timeout(self, tool, ctx):
        r = await tool.execute(
            ctx,
            {
                "command": 'python -c "import time; time.sleep(3)"',
                "timeout": 1,
            },
        )
        assert r.is_error
        assert "timed out" in r.content.lower()
        assert r.metadata["reason"] == "timeout"

    @pytest.mark.asyncio
    async def test_output_truncation(self, tool, ctx):
        # Print 20000 'x's. The tool should truncate to head 2000 + tail 8000.
        r = await tool.execute(
            ctx,
            {"command": "python -c \"print('x'*20000)\""},
        )
        assert not r.is_error
        assert r.metadata["truncated"] is True
        assert "truncated" in r.content
        # The body must be shorter than the raw output.
        assert r.metadata["raw_chars"] >= 20000


class TestBashValidation:
    def test_empty_command(self, tool):
        assert tool.validate_input({"command": ""})

    def test_timeout_too_low(self, tool):
        assert tool.validate_input({"command": "x", "timeout": 0})

    def test_timeout_too_high(self, tool):
        assert tool.validate_input({"command": "x", "timeout": 99999})

    def test_valid(self, tool):
        assert tool.validate_input({"command": "echo x"}) is None
        assert tool.validate_input({"command": "echo x", "timeout": 5}) is None
