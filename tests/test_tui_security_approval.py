import pytest
from textual.widgets import Static

from mewcode.engine.security.models import ExecutionRequest, OperationKind
from mewcode.engine.tools import WriteFileTool
from mewcode.tui.app import MewCodeApp
from mewcode.tui.widgets.chat_area import ChatArea


@pytest.mark.asyncio
async def test_approval_card_shows_safe_operation_details_and_choices():
    app = MewCodeApp()
    async with app.run_test() as pilot:
        chat = app.query_one("#chat-area", ChatArea)
        chat.add_approval_request(
            "request-1", "WriteFile", "private.txt",
            {"operation": "write", "risk": "moderate", "resource_summary": "file: private.txt"},
        )
        await pilot.pause()
        text = "\n".join(
            widget.content.plain if hasattr(widget.content, "plain") else str(widget.content)
            for widget in app.query(Static)
        )

    assert "Operation: write" in text
    assert "Risk: moderate" in text
    assert "/approve-request request-1" in text
    assert "/deny-request request-1" in text


@pytest.mark.asyncio
async def test_audit_command_only_shows_safe_summary():
    app = MewCodeApp()
    app.config["security"] = {"enabled": True}
    app.tool_registry.register(WriteFileTool()) if app.tool_registry.get("WriteFile") is None else None
    from mewcode.engine.security.gateway import ExecutionGateway
    app.execution_gateway = ExecutionGateway(app.tool_registry)
    await app.execution_gateway.execute(
        ExecutionRequest("WriteFile", {"path": "secret.txt", "content": "secret"}, operation=OperationKind.WRITE)
    )
    async with app.run_test() as pilot:
        app._handle_command("/audit")
        await pilot.pause()
        chat = app.query_one("#chat-area", ChatArea)
        content = "\n".join(message["content"] for message in chat._messages)

    assert "Recent security audit" in content
    assert "WriteFile" in content
    assert "secret" not in content
