"""Security primitives shared by local, external, and delegated execution."""

from .models import ApprovalScope, ExecutionRequest, OperationKind, PermissionDecision, PermissionGrant, RiskLevel
from .approval import ApprovalManager, ApprovalRequest, ApprovalStatus
from .workspace import WorkspaceViolation, resolve_in_workspace, summarize_resource
from .policy import PermissionStore, decide

__all__ = [
    "ExecutionRequest",
    "ApprovalScope",
    "PermissionGrant",
    "OperationKind",
    "PermissionDecision",
    "RiskLevel",
    "WorkspaceViolation",
    "resolve_in_workspace",
    "summarize_resource",
    "PermissionStore",
    "decide",
    "ApprovalManager",
    "ApprovalRequest",
    "ApprovalStatus",
]
