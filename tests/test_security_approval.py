import asyncio

import pytest

from mewcode.engine.security import (
    ApprovalManager,
    ApprovalStatus,
    ExecutionRequest,
    PermissionDecision,
)


@pytest.mark.asyncio
async def test_wait_returns_approval_and_removes_pending_request():
    manager = ApprovalManager()
    request = manager.create(ExecutionRequest("WriteFile", {}))

    waiter = asyncio.create_task(manager.wait(request))
    assert manager.resolve(request.request_id, approved=True) is request

    assert await waiter is PermissionDecision.ALLOW
    assert request.request_id not in manager.pending


@pytest.mark.asyncio
async def test_timeout_denies_without_leaving_pending_request():
    manager = ApprovalManager(default_timeout_seconds=0.01)
    request = manager.create(ExecutionRequest("Bash", {}))

    assert await manager.wait(request) is PermissionDecision.DENY
    assert request.status is ApprovalStatus.TIMED_OUT
    assert request.request_id not in manager.pending


@pytest.mark.asyncio
async def test_cancel_denies_waiting_request_and_hides_raw_input():
    manager = ApprovalManager()
    request = manager.create(ExecutionRequest("WriteFile", {"content": "secret"}))

    assert manager.cancel(request.request_id) is request
    assert await manager.wait(request) is PermissionDecision.DENY
    assert request.status is ApprovalStatus.CANCELLED
    assert "content" not in request.summary
