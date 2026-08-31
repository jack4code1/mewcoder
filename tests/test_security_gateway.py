import pytest
import json
from concurrent.futures import ThreadPoolExecutor

from mewcode.engine.security.gateway import ExecutionGateway
from mewcode.engine.security.audit import AuditLog
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
    assert gateway.audit[-1]["event_type"] == "approval_required"
    assert gateway.audit[-1]["approval_request_id"] == result.metadata["request_id"]
    assert "timestamp" in gateway.audit[-1]
    request_id = result.metadata["request_id"]
    approved = await gateway.approve(request_id)
    assert approved.is_error is False
    completed = await gateway.wait_for_approval(request_id)
    assert completed.is_error is False
    assert (tmp_path / "new.txt").read_text() == "hello"
    assert gateway.audit[-1]["status"] == "executed"
    assert gateway.audit[-1]["event_type"] == "executed"


@pytest.mark.asyncio
async def test_gateway_memory_and_jsonl_events_share_timestamp(tmp_path):
    registry = ToolRegistry(ToolContext.detect(tmp_path))
    registry.register(WriteFileTool())
    audit_log = AuditLog(tmp_path)
    gateway = ExecutionGateway(registry, audit_log=audit_log)

    result = await gateway.execute(
        ExecutionRequest(
            "WriteFile",
            {"path": "new.txt", "content": "hello"},
            operation=OperationKind.WRITE,
        )
    )
    assert result.metadata["audit"]["timestamp"] == gateway.audit[-1]["timestamp"]
    persisted = json.loads(audit_log.path.read_text(encoding="utf-8").splitlines()[0])
    assert persisted == gateway.audit[-1]


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
    assert gateway.audit[-1]["event_type"] == "rejected"


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
    assert gateway.audit[-1]["event_type"] == "cancelled"


@pytest.mark.asyncio
async def test_gateway_timeout_is_audited(tmp_path):
    registry = ToolRegistry(ToolContext.detect(tmp_path))
    registry.register(WriteFileTool())
    from mewcode.engine.security.approval import ApprovalManager

    gateway = ExecutionGateway(registry, approvals=ApprovalManager(default_timeout_seconds=0.001))
    initial = await gateway.execute(
        ExecutionRequest("WriteFile", {"path": "new.txt", "content": "hello"}, operation=OperationKind.WRITE)
    )
    result = await gateway.wait_for_approval(initial.metadata["request_id"])

    assert result.metadata["reason"] == "approval_timed_out"
    assert gateway.audit[-1]["event_type"] == "timeout"


def test_gateway_memory_audit_snapshot_is_thread_safe(tmp_path):
    registry = ToolRegistry(ToolContext.detect(tmp_path))
    registry.register(WriteFileTool())
    gateway = ExecutionGateway(registry)

    def record(index: int) -> None:
        gateway._record({"event_type": "executed", "tool_name": "WriteFile", "request_id": str(index)})

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(record, range(100)))

    entries = gateway.recent_audit(100)
    assert len(entries) == 100
    assert len({entry["request_id"] for entry in entries}) == 100
