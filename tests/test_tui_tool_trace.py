"""Tests for ChatArea tool-call trace rendering."""

import pytest
from textual.widgets import Static

from mewcode.tui.app import MewCodeApp
from mewcode.tui.widgets.chat_area import ChatArea


def _plain(widget: Static) -> str:
    return widget.content.plain


@pytest.mark.asyncio
async def test_tool_trace_pending_state():
    app = MewCodeApp()
    async with app.run_test() as pilot:
        chat = app.query_one("#chat-area", ChatArea)
        widget_id = chat.add_tool_call("ReadFile", "config.yaml")
        await pilot.pause(0.1)

        widget = app.query_one(f"#{widget_id}", Static)
        text = _plain(widget)

        assert "→" in text
        assert "ReadFile" in text
        assert "config.yaml" in text


@pytest.mark.asyncio
async def test_tool_trace_success_state():
    app = MewCodeApp()
    async with app.run_test() as pilot:
        chat = app.query_one("#chat-area", ChatArea)
        widget_id = chat.add_tool_call("ReadFile", "config.yaml")
        chat.update_tool_call_result(widget_id, success=True, summary="ok")
        await pilot.pause(0.1)

        widget = app.query_one(f"#{widget_id}", Static)
        text = _plain(widget)

        assert "✓" in text
        assert "ReadFile" in text
        assert "config.yaml" in text
        assert "ok" in text


@pytest.mark.asyncio
async def test_tool_trace_error_state():
    app = MewCodeApp()
    async with app.run_test() as pilot:
        chat = app.query_one("#chat-area", ChatArea)
        widget_id = chat.add_tool_call("ReadFile", "missing.txt")
        chat.update_tool_call_result(
            widget_id,
            success=False,
            summary="File not found",
        )
        await pilot.pause(0.1)

        widget = app.query_one(f"#{widget_id}", Static)
        text = _plain(widget)

        assert "✗" in text
        assert "ReadFile" in text
        assert "missing.txt" in text
        assert "File not found" in text
