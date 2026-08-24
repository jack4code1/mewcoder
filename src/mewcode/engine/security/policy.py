"""Default-deny policy for operations that can change state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path

from .models import ApprovalScope, ExecutionRequest, OperationKind, PermissionDecision, PermissionGrant


@dataclass
class PermissionStore:
    """In-memory grants scoped to one project runtime."""

    allowed_tools: set[str] = field(default_factory=set)
    project_tools: set[str] = field(default_factory=set)
    one_time_tools: set[str] = field(default_factory=set)
    grants: list[PermissionGrant] = field(default_factory=list)
    workspace: Path | None = None

    def grant(self, tool_name: str, *, expires_at: datetime | None = None) -> PermissionGrant:
        self.allowed_tools.add(tool_name)
        grant = PermissionGrant(tool_name, ApprovalScope.SESSION, expires_at=expires_at)
        self.grants.append(grant)
        return grant

    def grant_once(self, tool_name: str) -> PermissionGrant:
        self.one_time_tools.add(tool_name)
        grant = PermissionGrant(tool_name, ApprovalScope.ONCE)
        self.grants.append(grant)
        return grant

    def revoke(self, tool_name: str) -> None:
        self.allowed_tools.discard(tool_name)
        self.one_time_tools.discard(tool_name)
        self.grants = [grant for grant in self.grants if grant.tool_name != tool_name]

    def allows(self, tool_name: str) -> bool:
        self._remove_expired()
        return tool_name in self.allowed_tools or tool_name in self.project_tools or tool_name in self.one_time_tools

    def consume_once(self, tool_name: str) -> bool:
        if tool_name not in self.one_time_tools:
            return False
        self.one_time_tools.remove(tool_name)
        self.grants = [
            grant for grant in self.grants
            if not (grant.tool_name == tool_name and grant.scope is ApprovalScope.ONCE)
        ]
        return True

    def _remove_expired(self) -> None:
        now = datetime.now(timezone.utc)
        expired = {
            grant.tool_name for grant in self.grants
            if grant.expires_at is not None and grant.expires_at.astimezone(timezone.utc) <= now
        }
        for tool_name in expired:
            self.allowed_tools.discard(tool_name)
        self.grants = [
            grant for grant in self.grants
            if grant.expires_at is None or grant.expires_at.astimezone(timezone.utc) > now
        ]

    def grant_project(self, tool_name: str) -> PermissionGrant:
        self.project_tools.add(tool_name)
        grant = PermissionGrant(
            tool_name, ApprovalScope.PROJECT,
            workspace=str(self.workspace) if self.workspace else None,
        )
        self.grants.append(grant)
        return grant

    def revoke_project(self, tool_name: str) -> None:
        self.project_tools.discard(tool_name)
        self.grants = [
            grant for grant in self.grants
            if not (grant.tool_name == tool_name and grant.scope is ApprovalScope.PROJECT)
        ]

    def load_project(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        path = workspace / ".mewcode" / "permissions.json"
        self.project_tools = set()
        self.grants = [
            grant for grant in self.grants if grant.scope is not ApprovalScope.PROJECT
        ]
        if path.exists():
            self.project_tools = set(json.loads(path.read_text(encoding="utf-8")).get("tools", []))

    def save_project(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        path = workspace / ".mewcode" / "permissions.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"tools": sorted(self.project_tools)}), encoding="utf-8")


def decide(request: ExecutionRequest, grants: PermissionStore | None = None) -> PermissionDecision:
    """Allow reads; require approval for all operations that may change state."""
    if request.operation is OperationKind.READ:
        return PermissionDecision.ALLOW
    if grants is not None and grants.allows(request.tool_name):
        grants.consume_once(request.tool_name)
        return PermissionDecision.ALLOW
    return PermissionDecision.REQUIRE_APPROVAL
