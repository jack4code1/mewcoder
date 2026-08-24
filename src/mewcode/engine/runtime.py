"""Project-scoped runtime state shared by agent services."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .security.policy import PermissionStore


@dataclass
class ProjectRuntime:
    """Mutable state is isolated by one resolved workspace root."""

    workspace: Path
    context_budget: int = 16_000
    permissions: PermissionStore = field(default_factory=PermissionStore)

    def __post_init__(self) -> None:
        self.workspace = self.workspace.resolve()
        self.permissions.load_project(self.workspace)

