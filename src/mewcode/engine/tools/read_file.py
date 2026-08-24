"""ReadFile tool: read a text file with line numbers, paged.

Refuses binary files (sniffs the first 512 bytes for NUL).
"""

from __future__ import annotations

from typing import Any, Optional

from .base import Tool, ToolContext, ToolResult
from ..security.models import OperationKind, RiskLevel


_BINARY_SNIFF_BYTES = 512


class ReadFileTool(Tool):
    name = "ReadFile"
    description = (
        "Read the contents of a text file from disk.\n"
        "WHEN TO USE: After locating a file with Grep or Glob, or when the user "
        "names a file directly. Always read before editing.\n"
        "WHEN NOT TO USE: For binary files (use Bash with appropriate inspection "
        "tools). To search across many files (use Grep). To list files (use Glob).\n"
        "PATH: Absolute or relative to the working directory.\n"
        "PAGING: Use offset (1-based line index, default 1) and limit (max lines, "
        "default the whole file) to read large files in chunks.\n"
        "RETURN FORMAT: Each line is prefixed with its 1-based line number and a "
        "tab, e.g. `1\\tdef main():`. The line numbers always reflect positions "
        "in the file even when paging."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path (absolute or relative to the working directory).",
            },
            "offset": {
                "type": "integer",
                "minimum": 1,
                "description": "1-based line index to start reading from. Default 1.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "description": "Maximum number of lines to return. Default: read to end of file.",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }
    category = "file"
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True
    operation_kind = OperationKind.READ
    risk_level = RiskLevel.LOW

    def validate_input(self, input: dict[str, Any]) -> Optional[str]:
        path = input.get("path")
        if not isinstance(path, str) or not path.strip():
            return "path is required and must be a non-empty string"
        offset = input.get("offset")
        if offset is not None and (not isinstance(offset, int) or offset < 1):
            return "offset must be an integer >= 1"
        limit = input.get("limit")
        if limit is not None and (not isinstance(limit, int) or limit < 1):
            return "limit must be an integer >= 1"
        return None

    async def execute(
        self, ctx: ToolContext, input: dict[str, Any]
    ) -> ToolResult:
        raw_path = input["path"]
        offset = input.get("offset", 1)
        limit = input.get("limit")

        try:
            p = ctx.resolve_path(raw_path)
        except Exception as e:  # noqa: BLE001
            return ToolResult(
                content=f"Invalid path {raw_path!r}: {e}",
                is_error=True,
                metadata={"path": raw_path},
            )

        if not p.exists():
            return ToolResult(
                content=f"File not found: {p}",
                is_error=True,
                metadata={"path": str(p)},
            )
        if not p.is_file():
            return ToolResult(
                content=f"Not a regular file: {p}",
                is_error=True,
                metadata={"path": str(p)},
            )

        # Binary sniff.
        try:
            with p.open("rb") as fh:
                head = fh.read(_BINARY_SNIFF_BYTES)
        except OSError as e:
            return ToolResult(
                content=f"Failed to open {p}: {e}",
                is_error=True,
                metadata={"path": str(p)},
            )
        if b"\x00" in head:
            return ToolResult(
                content=(
                    f"Binary file detected: {p}. "
                    "Use Bash with an appropriate inspection tool (file/xxd/hexdump) instead."
                ),
                is_error=True,
                metadata={"path": str(p), "reason": "binary"},
            )

        # Read full text (utf-8, lossy on undecodable bytes).
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return ToolResult(
                content=f"Failed to read {p}: {e}",
                is_error=True,
                metadata={"path": str(p)},
            )

        lines = text.splitlines()
        total = len(lines)

        start_idx = offset - 1  # convert to 0-based
        if start_idx >= total and total > 0:
            return ToolResult(
                content=(
                    f"offset {offset} is past end of file (total {total} lines)."
                ),
                is_error=True,
                metadata={"path": str(p), "total_lines": total},
            )

        end_idx = total if limit is None else min(total, start_idx + limit)
        chunk = lines[start_idx:end_idx]

        body_lines = [f"{start_idx + i + 1}\t{line}" for i, line in enumerate(chunk)]
        body = "\n".join(body_lines)

        if total == 0:
            body = "(empty file)"

        suffix = ""
        if end_idx < total:
            suffix = (
                f"\n\n... [{total - end_idx} more lines, "
                f"call ReadFile again with offset={end_idx + 1}] ..."
            )

        return ToolResult(
            content=body + suffix,
            is_error=False,
            metadata={
                "path": str(p),
                "total_lines": total,
                "returned_lines": len(chunk),
                "offset": offset,
                "limit": limit,
            },
        )
