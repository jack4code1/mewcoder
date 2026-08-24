"""Workspace containment and human-readable resource summaries."""

from __future__ import annotations

from pathlib import Path


class WorkspaceViolation(ValueError):
    """Raised when a path resolves outside the selected project workspace."""


def resolve_in_workspace(workspace: Path, raw_path: str) -> Path:
    root = workspace.resolve()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise WorkspaceViolation(f"path escapes workspace {root}") from exc
    return resolved


def summarize_resource(path: Path) -> str:
    """Return a display-safe description without reading file contents."""
    return f"file: {path}"
