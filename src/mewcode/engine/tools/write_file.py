"""WriteFile tool: create or overwrite a text file, creating parent dirs."""

from __future__ import annotations

from typing import Any, Optional

from .base import Tool, ToolContext, ToolResult
from ..security.models import OperationKind, RiskLevel


class WriteFileTool(Tool):
    name = "WriteFile"
    description = (
        "Write content to a file, creating parent directories if needed. "
        "Overwrites the file if it already exists.\n"
        "WHEN TO USE: Creating a new file, or fully replacing the contents of an "
        "existing file when most of it is changing.\n"
        "WHEN NOT TO USE: Making a small change to an existing file — use EditFile "
        "instead so you don't accidentally clobber unrelated content.\n"
        "PATH: Absolute or relative to the working directory.\n"
        "ENCODING: UTF-8."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path (absolute or relative to the working directory).",
            },
            "content": {
                "type": "string",
                "description": "Full file content. Existing file (if any) is overwritten.",
            },
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }
    category = "file"
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False
    operation_kind = OperationKind.WRITE
    risk_level = RiskLevel.MODERATE

    def validate_input(self, input: dict[str, Any]) -> Optional[str]:
        path = input.get("path")
        if not isinstance(path, str) or not path.strip():
            return "path is required and must be a non-empty string"
        content = input.get("content")
        if not isinstance(content, str):
            return "content is required and must be a string"
        return None

    async def execute(
        self, ctx: ToolContext, input: dict[str, Any]
    ) -> ToolResult:
        raw_path = input["path"]
        content = input["content"]

        try:
            p = ctx.resolve_path(raw_path)
        except Exception as e:  # noqa: BLE001
            return ToolResult(
                content=f"Invalid path {raw_path!r}: {e}",
                is_error=True,
                metadata={"path": raw_path},
            )

        if p.exists() and p.is_dir():
            return ToolResult(
                content=f"Cannot write: {p} is a directory.",
                is_error=True,
                metadata={"path": str(p)},
            )

        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        except OSError as e:
            return ToolResult(
                content=f"Failed to write {p}: {e}",
                is_error=True,
                metadata={"path": str(p)},
            )

        return ToolResult(
            content=f"Wrote {len(content)} bytes to {p}",
            is_error=False,
            metadata={"path": str(p), "bytes": len(content)},
        )
