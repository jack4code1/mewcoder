"""Read-only Git diff inspection tool."""

from __future__ import annotations

import asyncio

from .base import Tool, ToolContext, ToolResult


class DiffTool(Tool):
    name = "Diff"
    description = "Show uncommitted Git changes, optionally limited to one workspace-relative path."
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Optional workspace-relative path."}},
        "additionalProperties": False,
    }
    category = "file"
    is_read_only = True
    is_concurrency_safe = True

    async def execute(self, ctx: ToolContext, input: dict) -> ToolResult:
        path = input.get("path")
        if path is not None and (not isinstance(path, str) or not path.strip()):
            return ToolResult("path must be a non-empty string when provided.", is_error=True)
        command = ["git", "diff", "--"]
        if path:
            command.append(path)
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(ctx.working_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
        except (OSError, asyncio.TimeoutError) as exc:
            return ToolResult(f"Diff failed: {exc}", is_error=True)
        if process.returncode:
            return ToolResult(f"Diff failed: {stderr.decode(errors='replace')}", is_error=True)
        output = stdout.decode(errors="replace")
        return ToolResult(output or "No uncommitted changes.")
