import pytest

from mewcode.tui.app import MewCodeApp
from mewcode.tui.widgets.chat_area import ChatArea


@pytest.mark.asyncio
async def test_mcp_command_reports_empty_configuration():
    app = MewCodeApp()
    async with app.run_test() as pilot:
        app._handle_command("/mcp")
        await pilot.pause()
        chat = app.query_one("#chat-area", ChatArea)

    assert chat._messages[-1]["content"] == "No MCP servers configured."
