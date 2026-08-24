"""Awaitable approval requests used by the policy/UI boundary."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from time import monotonic
from typing import Any
from uuid import uuid4

from .models import ExecutionRequest, PermissionDecision


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class ApprovalRequest:
    execution: ExecutionRequest
    timeout_seconds: float
    request_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: float = field(default_factory=monotonic)
    status: ApprovalStatus = ApprovalStatus.PENDING
    decision: PermissionDecision | None = None
    _resolved: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    @property
    def summary(self) -> dict[str, Any]:
        """Safe data for an approval UI; raw tool arguments stay private."""
        return {
            "request_id": self.request_id,
            "tool_name": self.execution.tool_name,
            "source": self.execution.source,
            "operation": self.execution.operation.value,
            "risk": self.execution.risk.value,
            "resource_summary": self.execution.resource_summary,
        }


class ApprovalManager:
    """Owns pending approvals and turns timeout/cancel into explicit results."""

    def __init__(self, default_timeout_seconds: float = 300) -> None:
        self.default_timeout_seconds = default_timeout_seconds
        self.pending: dict[str, ApprovalRequest] = {}

    def create(self, execution: ExecutionRequest, *, timeout_seconds: float | None = None) -> ApprovalRequest:
        request = ApprovalRequest(
            execution=execution,
            timeout_seconds=self.default_timeout_seconds if timeout_seconds is None else timeout_seconds,
        )
        self.pending[request.request_id] = request
        return request

    def resolve(self, request_id: str, approved: bool) -> ApprovalRequest | None:
        request = self.pending.get(request_id)
        if request is None or request.status is not ApprovalStatus.PENDING:
            return None
        request.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED
        request.decision = PermissionDecision.ALLOW if approved else PermissionDecision.DENY
        request._resolved.set()
        return request

    def cancel(self, request_id: str) -> ApprovalRequest | None:
        request = self.pending.get(request_id)
        if request is None or request.status is not ApprovalStatus.PENDING:
            return None
        request.status = ApprovalStatus.CANCELLED
        request.decision = PermissionDecision.DENY
        request._resolved.set()
        return request

    async def wait(self, request: ApprovalRequest) -> PermissionDecision:
        try:
            await asyncio.wait_for(request._resolved.wait(), request.timeout_seconds)
        except asyncio.TimeoutError:
            if request.status is ApprovalStatus.PENDING:
                request.status = ApprovalStatus.TIMED_OUT
                request.decision = PermissionDecision.DENY
        finally:
            self.pending.pop(request.request_id, None)
        return request.decision or PermissionDecision.DENY
