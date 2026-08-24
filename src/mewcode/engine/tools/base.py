"""Core types for the tool subsystem.

Defines:
  - ToolError: sentinel exception for unrecoverable system-level failures.
  - ToolResult: the return value of every tool execution (success and failure).
  - ToolContext: runtime context passed into every tool execution.
  - Tool: abstract base class for all tools.
"""

from __future__ import annotations

import platform
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..security.models import OperationKind, RiskLevel
from ..security.workspace import resolve_in_workspace, summarize_resource


class ToolError(Exception):
    """Sentinel exception for unrecoverable system-level failures.

    Tools must NOT raise this for recoverable conditions (file missing,
    invalid parameters, command failed, etc.) — those are returned as
    ToolResult(is_error=True). ToolError is reserved for true system
    breakage (OOM, runtime corruption) and is allowed to propagate.
    """


@dataclass
class ToolResult:
    """Return value of a tool execution.

    Attributes:
        content: Text shown to the model. English. For errors this is the
            human-readable error explanation.
        is_error: Whether this is an error result. Maps to OpenAI tool-message
            error semantics or Anthropic tool_result.is_error in adapters.
        metadata: UI-only auxiliary data (path, command, duration_ms, ...).
            Never enters the LLM context.
    """

    content: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolContext:
    """Runtime context for tool execution.

    Locked at MewCodeApp startup and reused across all tool executions.

    Attributes:
        working_dir: Absolute path locked at startup (os.getcwd()). All
            relative paths resolve against this.
        os_name: 'windows' / 'darwin' / 'linux'.
        platform_shell: 'cmd' / 'powershell' / 'sh'. Used by BashTool.
    """

    working_dir: Path
    os_name: str
    platform_shell: str

    def resolve_path(self, p: str) -> Path:
        """Resolve a tool-supplied path string.

        Absolute paths are kept as-is. Relative paths are joined onto
        working_dir. The result is fully resolved (symlinks etc. follow
        OS defaults — see spec N6).
        """
        try:
            return resolve_in_workspace(self.working_dir, p)
        except OSError:
            # If the path can't be fully resolved (e.g. permission), keep
            # the unresolved absolute path so the caller can produce a
            # meaningful error result instead of crashing.
            path = Path(p)
            return path if path.is_absolute() else self.working_dir / path

    def preview_path(self, p: str) -> dict[str, str]:
        """Return a safe path preview for approval and audit UI."""
        path = self.resolve_path(p)
        return {"path": str(path), "resource_summary": summarize_resource(path)}

    @classmethod
    def detect(cls, working_dir: Optional[Path] = None) -> "ToolContext":
        """Build a context using the current process state."""
        wd = working_dir or Path.cwd()
        sysname = platform.system().lower()
        if "windows" in sysname:
            os_name = "windows"
            shell = "cmd"
        elif "darwin" in sysname:
            os_name = "darwin"
            shell = "sh"
        else:
            os_name = "linux"
            shell = "sh"
        return cls(working_dir=wd, os_name=os_name, platform_shell=shell)


class Tool(ABC):
    """Abstract base class for all tools.

    Subclasses fill the class attributes (name/description/input_schema/...)
    and override `execute`. Optionally override `validate_input` for
    semantic checks beyond JSON Schema.

    All strings exposed to the LLM (name, description, content of returned
    ToolResult, validate_input error messages) MUST be in English (spec N11).
    """

    # Class attributes populated by subclasses.
    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {}
    category: str = ""  # 'file' | 'shell' | 'search'
    is_read_only: bool = False
    is_destructive: bool = False
    is_concurrency_safe: bool = False
    operation_kind: OperationKind = OperationKind.READ
    risk_level: RiskLevel = RiskLevel.LOW

    def validate_input(self, input: dict[str, Any]) -> Optional[str]:
        """Semantic validation of input. Return English error string or None.

        Default implementation accepts any input. Subclasses override for
        semantic checks not expressible in JSON Schema (e.g. path emptiness,
        timeout range, regex compilability).
        """
        return None

    @abstractmethod
    async def execute(
        self, ctx: ToolContext, input: dict[str, Any]
    ) -> ToolResult:
        """Execute the tool.

        Implementations MUST wrap recoverable failures into
        ToolResult(is_error=True). Only raise ToolError for unrecoverable
        system-level conditions.
        """
        raise NotImplementedError
