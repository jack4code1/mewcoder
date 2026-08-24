"""Protocol-neutral models for controlled execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class OperationKind(str, Enum):
    READ = "read"
    WRITE = "write"
    COMMAND = "command"
    EXTERNAL = "external"
    ADMIN = "admin"


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class PermissionDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class ApprovalScope(str, Enum):
    """Lifetime of a user authorization for a controlled operation."""

    ONCE = "once"
    SESSION = "session"
    PROJECT = "project"


@dataclass(frozen=True)
class ExecutionRequest:
    """A tool invocation before policy evaluation or execution."""

    tool_name: str
    input: dict[str, Any]
    source: str = "agent"
    operation: OperationKind = OperationKind.READ
    risk: RiskLevel = RiskLevel.LOW
    request_id: str | None = None
    parent_task_id: str | None = None
    resource_summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PermissionGrant:
    """A narrowly scoped, revocable authorization record."""

    tool_name: str
    scope: ApprovalScope
    workspace: str | None = None
    expires_at: datetime | None = None
