"""Role-scoped tool permissions for delegated agents."""

from __future__ import annotations


ROLE_TOOL_POLICY: dict[str, set[str]] = {
    "analysis": {"Glob", "Grep", "ReadFile"},
    "researcher": {"Glob", "Grep", "ReadFile"},
    "coding": {"Glob", "Grep", "ReadFile", "EditFile", "WriteFile"},
    "implementer": {"Glob", "Grep", "ReadFile", "EditFile", "WriteFile"},
    "repairer": {"Glob", "Grep", "ReadFile", "EditFile", "WriteFile"},
    "test": {"ReadFile", "Bash"},
    "tester": {"ReadFile", "Bash"},
    "review": {"ReadFile", "Diff"},
    "reviewer": {"ReadFile", "Diff"},
}


def allowed_tools_for_role(
    role: str, registry_enabled: set[str], task_requested: set[str] | None = None
) -> set[str]:
    """Return the enforceable intersection for a delegated task.

    Unknown roles preserve the currently enabled Registry tools so the primary
    ReAct agent remains backward-compatible. Known roles are a hard maximum;
    Planner requests can only narrow that maximum further.
    """
    role_limit = ROLE_TOOL_POLICY.get(role.casefold(), registry_enabled)
    allowed = registry_enabled & role_limit
    return allowed if task_requested is None else allowed & task_requested
