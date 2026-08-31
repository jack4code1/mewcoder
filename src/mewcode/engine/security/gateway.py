"""Single policy gate for tool execution."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any

from ..tools.base import ToolResult
from ..tools.registry import ToolRegistry
from .approval import ApprovalManager, ApprovalStatus
from .audit import AuditLog, prepare_audit_entry
from .models import ApprovalScope, ExecutionRequest, PermissionDecision
from .policy import PermissionStore, decide
from .revisions import RevisionStore


@dataclass
class ExecutionGateway:
    registry: ToolRegistry
    grants: PermissionStore = field(default_factory=PermissionStore)
    audit: list[dict[str, Any]] = field(default_factory=list)
    audit_log: AuditLog | None = None
    approvals: ApprovalManager = field(default_factory=ApprovalManager)
    revisions: RevisionStore | None = None
    _audit_lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    @property
    def pending(self) -> dict[str, ExecutionRequest]:
        """Compatibility view of requests awaiting a user decision."""
        return {key: value.execution for key, value in self.approvals.pending.items()}

    def _record(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Normalize once so memory and disk receive the same timestamped event."""
        with self._audit_lock:
            normalized = (
                self.audit_log.prepare(entry)
                if self.audit_log is not None
                else prepare_audit_entry(entry)
            )
            self.audit.append(normalized)
            if self.audit_log is not None:
                self.audit_log.append(normalized)
            return normalized

    def recent_audit(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return a bounded snapshot for UI display without exposing raw inputs."""
        if limit <= 0:
            return []
        with self._audit_lock:
            return list(self.audit[-limit:])

    @staticmethod
    def _request_entry(
        request: ExecutionRequest,
        *,
        event_type: str,
        permission: str,
        decision: str,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "event_type": event_type,
            "tool_name": request.tool_name,
            # Compatibility key retained for existing consumers.
            "tool": request.tool_name,
            "source": request.source,
            "operation": request.operation.value,
            "risk": request.risk.value,
            "permission": permission,
            "decision": decision,
            "resource_summary": request.resource_summary,
        }
        metadata = request.metadata if isinstance(request.metadata, dict) else {}
        for key in ("agent", "caller", "session_id", "task_id"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                entry[key] = value
        if request.parent_task_id and "task_id" not in entry:
            entry["task_id"] = request.parent_task_id
        if isinstance(request.request_id, str) and request.request_id:
            entry["request_id"] = request.request_id
        return entry

    async def execute(self, request: ExecutionRequest) -> ToolResult:
        decision = decide(request, self.grants)
        entry = self._request_entry(
            request,
            event_type=(
                "approval_required"
                if decision is PermissionDecision.REQUIRE_APPROVAL
                else "executed"
            ),
            permission=decision.value,
            decision=decision.value,
        )
        if decision is PermissionDecision.REQUIRE_APPROVAL:
            approval = self.approvals.create(request)
            entry["request_id"] = approval.request_id
            entry["approval_request_id"] = approval.request_id
            entry["status"] = "pending"
            entry = self._record(entry)
            return ToolResult(
                content=f"Approval required before executing {request.tool_name}.",
                is_error=True,
                metadata={
                    "reason": "approval_required",
                    "request_id": approval.request_id,
                    "approval": approval.summary,
                    "audit": entry,
                },
            )
        revision = self._capture_revision(request)
        result = await self.registry.execute(request.tool_name, request.input)
        if revision is not None and not result.is_error:
            result.metadata.setdefault("revision_id", revision.id)
        entry["is_error"] = result.is_error
        entry["status"] = "executed"
        if result.is_error and isinstance(result.metadata.get("reason"), str):
            entry["error_reason"] = result.metadata["reason"]
        entry = self._record(entry)
        result.metadata.setdefault("audit", entry)
        return result

    def _capture_revision(self, request: ExecutionRequest):
        if self.revisions is None or request.tool_name not in {"WriteFile", "EditFile"}:
            return None
        raw_path = request.input.get("path")
        if not isinstance(raw_path, str):
            return None
        return self.revisions.capture(self.registry.ctx.resolve_path(raw_path))

    async def approve(self, request_id: str, *, project: bool = False) -> ToolResult:
        """Resolve an approval; the waiting Agent loop executes the request."""
        approval = self.approvals.pending.get(request_id)
        if approval is None:
            return ToolResult("No pending approval request with that id.", is_error=True)
        if project:
            self.grants.grant_project(approval.execution.tool_name)
        else:
            self.grants.grant_once(approval.execution.tool_name)
        self.approvals.resolve(request_id, approved=True)
        entry = self._request_entry(
            approval.execution,
            event_type="approved",
            permission=PermissionDecision.ALLOW.value,
            decision="approved",
        )
        entry["request_id"] = request_id
        entry["approval_request_id"] = request_id
        entry["authorization_scope"] = (
            ApprovalScope.PROJECT.value if project else ApprovalScope.ONCE.value
        )
        entry["status"] = "approved"
        self._record(entry)
        return ToolResult("Approval granted; waiting execution will continue.")

    async def wait_for_approval(self, request_id: str) -> ToolResult:
        approval = self.approvals.pending.get(request_id)
        if approval is None:
            return ToolResult("No pending approval request with that id.", is_error=True)
        decision = await self.approvals.wait(approval)
        request = approval.execution
        if decision is PermissionDecision.ALLOW:
            revision = self._capture_revision(request)
            result = await self.registry.execute(request.tool_name, request.input)
            if revision is not None and not result.is_error:
                result.metadata.setdefault("revision_id", revision.id)
            entry = self._request_entry(
                request,
                event_type="executed",
                permission=PermissionDecision.ALLOW.value,
                decision="allow",
            )
            entry["request_id"] = request_id
            entry["approval_request_id"] = request_id
            entry["status"] = "executed"
            entry["is_error"] = result.is_error
            if result.is_error and isinstance(result.metadata.get("reason"), str):
                entry["error_reason"] = result.metadata["reason"]
            entry = self._record(entry)
            result.metadata.setdefault("audit", entry)
            return result

        reason = {
            ApprovalStatus.DENIED: "approval_denied",
            ApprovalStatus.CANCELLED: "approval_cancelled",
            ApprovalStatus.TIMED_OUT: "approval_timed_out",
        }.get(approval.status, "approval_denied")
        event_type = {
            "approval_denied": "rejected",
            "approval_cancelled": "cancelled",
            "approval_timed_out": "timeout",
        }.get(reason, "rejected")
        entry = self._request_entry(
            request,
            event_type=event_type,
            permission=PermissionDecision.DENY.value,
            decision="deny",
        )
        entry["request_id"] = request_id
        entry["approval_request_id"] = request_id
        entry["reason"] = reason
        entry["status"] = {
            "rejected": "rejected",
            "cancelled": "cancelled",
            "timeout": "timed_out",
        }.get(event_type, event_type)
        entry = self._record(entry)
        return ToolResult(
            f"Approval was not granted for {request.tool_name}.",
            is_error=True,
            metadata={"reason": reason, "request_id": request_id, "audit": entry},
        )

    def deny(self, request_id: str) -> ToolResult:
        approval = self.approvals.resolve(request_id, approved=False)
        if approval is None:
            return ToolResult("No pending approval request with that id.", is_error=True)
        return ToolResult(
            f"Approval denied for {approval.execution.tool_name}.",
            metadata={"request_id": request_id},
        )

    def cancel_pending(self) -> None:
        """Release all waiting calls when their owning agent is cancelled."""
        for request_id in tuple(self.approvals.pending):
            self.approvals.cancel(request_id)
