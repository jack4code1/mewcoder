"""MewCode tool subsystem.

This package hosts the tool abstraction (`Tool`, `ToolResult`, `ToolContext`),
the registry, the six built-in tools, and the system-prompt builder.
"""

from typing import Any

from .base import Tool, ToolContext, ToolError, ToolResult
from .registry import ToolRegistry
from .read_file import ReadFileTool
from .write_file import WriteFileTool
from .edit_file import EditFileTool
from .bash import BashTool
from .glob import GlobTool
from .grep import GrepTool
from .diff import DiffTool
from .system_prompt import build_system_prompt


__all__ = [
    "Tool",
    "ToolContext",
    "ToolError",
    "ToolResult",
    "ToolRegistry",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "BashTool",
    "GlobTool",
    "GrepTool",
    "DiffTool",
    "build_system_prompt",
    "build_default_registry",
]


_BUILTIN_TOOL_CLASSES = (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    BashTool,
    GlobTool,
    GrepTool,
    DiffTool,
)


def build_default_registry(
    ctx: ToolContext, config: dict[str, Any]
) -> ToolRegistry:
    """Construct the registry with the built-in tools and apply config.

    Reads `config["tools"]["enabled"]` to decide which tools to enable:
      - "all" (default): every registered tool.
      - "readonly": only is_read_only tools.
      - list[str]: explicit tool names.
    Missing or empty config → "all".
    """
    registry = ToolRegistry(ctx)
    for cls in _BUILTIN_TOOL_CLASSES:
        registry.register(cls())

    tools_cfg = (config or {}).get("tools") or {}
    enabled = tools_cfg.get("enabled", "all")
    if enabled in (None, "", []):
        enabled = "all"
    registry.enable(enabled)
    return registry
