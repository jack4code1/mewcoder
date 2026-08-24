import pytest

from mewcode.engine.security.gateway import ExecutionGateway
from mewcode.engine.security.models import ExecutionRequest, OperationKind
from mewcode.engine.tools import ToolContext, ToolRegistry, WriteFileTool


@pytest.mark.asyncio
async def test_gateway_requires_approval_for_write(tmp_path):
    registry = ToolRegistry(ToolContext.detect(tmp_path))
    registry.register(WriteFileTool())
    gateway = ExecutionGateway(registry)

    result = await gateway.execute(
        ExecutionRequest("WriteFile", {"path": "new.txt", "content": "hello"}, operation=OperationKind.WRITE)
    )

    assert result.is_error is True
    assert result.metadata["reason"] == "approval_required"
    assert not (tmp_path / "new.txt").exists()
    assert gateway.audit[-1]["decision"] == "require_approval"
    request_id = result.metadata["request_id"]
    approved = await gateway.approve(request_id)
    assert approved.is_error is False
    completed = await gateway.wait_for_approval(request_id)
    assert completed.is_error is False
    assert (tmp_path / "new.txt").read_text() == "hello"
    assert gateway.audit[-1]["status"] == "executed"


@pytest.mark.asyncio
async def test_gateway_executes_explicitly_granted_write(tmp_path):
    registry = ToolRegistry(ToolContext.detect(tmp_path))
    registry.register(WriteFileTool())
    gateway = ExecutionGateway(registry)
    gateway.grants.grant("WriteFile")

    result = await gateway.execute(
        ExecutionRequest("WriteFile", {"path": "new.txt", "content": "hello"}, operation=OperationKind.WRITE)
    )

    assert result.is_error is False
    assert (tmp_path / "new.txt").read_text() == "hello"
    assert gateway.audit[-1]["decision"] == "allow"


@pytest.mark.asyncio
async def test_gateway_denial_returns_model_safe_result_and_leaves_no_pending(tmp_path):
    registry = ToolRegistry(ToolContext.detect(tmp_path))
    registry.register(WriteFileTool())
    gateway = ExecutionGateway(registry)

    initial = await gateway.execute(
        ExecutionRequest("WriteFile", {"path": "new.txt", "content": "hello"}, operation=OperationKind.WRITE)
    )
    request_id = initial.metadata["request_id"]
    assert gateway.deny(request_id).is_error is False

    result = await gateway.wait_for_approval(request_id)
    assert result.is_error is True
    assert result.metadata["reason"] == "approval_denied"
    assert not gateway.pending
    assert not (tmp_path / "new.txt").exists()


@pytest.mark.asyncio
async def test_gateway_cancellation_releases_all_pending_requests(tmp_path):
    registry = ToolRegistry(ToolContext.detect(tmp_path))
    registry.register(WriteFileTool())
    gateway = ExecutionGateway(registry)
    initial = await gateway.execute(
        ExecutionRequest("WriteFile", {"path": "new.txt", "content": "hello"}, operation=OperationKind.WRITE)
    )

    gateway.cancel_pending()
    result = await gateway.wait_for_approval(initial.metadata["request_id"])

    assert result.metadata["reason"] == "approval_cancelled"
    assert not gateway.pending
