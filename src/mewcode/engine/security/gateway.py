"""Single policy gate for tool execution."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..tools.base import ToolResult
from ..tools.registry import ToolRegistry
from .approval import ApprovalManager, ApprovalStatus
from .models import ApprovalScope, ExecutionRequest, PermissionDecision
from .policy import PermissionStore, decide
from .audit import AuditLog
from .revisions import RevisionStore


@dataclass
class ExecutionGateway:
    registry: ToolRegistry
    grants: PermissionStore = field(default_factory=PermissionStore)
    audit: list[dict] = field(default_factory=list)
    audit_log: AuditLog | None = None
    approvals: ApprovalManager = field(default_factory=ApprovalManager)
    revisions: RevisionStore | None = None

    @property
    def pending(self) -> dict[str, ExecutionRequest]:
        """Compatibility view of requests awaiting a user decision."""
        return {key: value.execution for key, value in self.approvals.pending.items()}

    def _record(self, entry: dict) -> dict:
        self.audit.append(entry)
        if self.audit_log is not None:
            self.audit_log.append(entry)
        return entry

    async def execute(self, request: ExecutionRequest) -> ToolResult:
        decision = decide(request, self.grants)
        entry = {
            "tool": request.tool_name,
            "source": request.source,
            "decision": decision.value,
            "resource_summary": request.resource_summary,
        }
        if decision is PermissionDecision.REQUIRE_APPROVAL:
            approval = self.approvals.create(request)
            entry["request_id"] = approval.request_id
            self._record(entry)
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
        self._record(entry)
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
        self._record({
            "tool": approval.execution.tool_name,
            "source": approval.execution.source,
            "request_id": request_id,
            "decision": "approved",
            "scope": ApprovalScope.PROJECT.value if project else ApprovalScope.ONCE.value,
        })
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
            entry = {
                "tool": request.tool_name,
                "source": request.source,
                "request_id": request_id,
                "decision": "allow",
                "status": "executed",
                "is_error": result.is_error,
            }
            self._record(entry)
            result.metadata.setdefault("audit", entry)
            return result

        reason = {
            ApprovalStatus.DENIED: "approval_denied",
            ApprovalStatus.CANCELLED: "approval_cancelled",
            ApprovalStatus.TIMED_OUT: "approval_timed_out",
        }.get(approval.status, "approval_denied")
        entry = {
            "tool": request.tool_name,
            "source": request.source,
            "request_id": request_id,
            "decision": "deny",
            "reason": reason,
        }
        self._record(entry)
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
