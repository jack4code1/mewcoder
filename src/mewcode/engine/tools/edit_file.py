"""EditFile tool: replace a unique string within a file."""

from __future__ import annotations

from typing import Any, Optional

from .base import Tool, ToolContext, ToolResult


_PREVIEW_CONTEXT_LINES = 5


class EditFileTool(Tool):
    name = "EditFile"
    description = (
        "Replace a unique snippet within a file.\n"
        "WHEN TO USE: Making a localized change to an existing file. Always read "
        "the file (with ReadFile) right before editing.\n"
        "WHEN NOT TO USE: Creating a brand new file (use WriteFile) or rewriting "
        "most of a file (use WriteFile).\n"
        "old_string MUST appear EXACTLY ONCE in the file. If it appears multiple "
        "times, the call fails — extend old_string with surrounding context (more "
        "lines above/below) until it's unique. Whitespace and indentation are "
        "compared literally.\n"
        "If old_string is not found, your snapshot of the file is likely stale; "
        "re-read it and try again.\n"
        "An empty new_string deletes the matched snippet.\n"
        "RETURN FORMAT: confirmation plus a numbered preview of the changed area."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path (absolute or relative to the working directory).",
            },
            "old_string": {
                "type": "string",
                "description": "Snippet to replace. Must occur exactly once in the file.",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement text. Use empty string to delete the snippet.",
            },
        },
        "required": ["path", "old_string", "new_string"],
        "additionalProperties": False,
    }
    category = "file"
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False

    def validate_input(self, input: dict[str, Any]) -> Optional[str]:
        path = input.get("path")
        if not isinstance(path, str) or not path.strip():
            return "path is required and must be a non-empty string"
        old = input.get("old_string")
        if not isinstance(old, str) or old == "":
            return "old_string is required and must be a non-empty string"
        new = input.get("new_string")
        if not isinstance(new, str):
            return "new_string is required and must be a string (use \"\" to delete)"
        if old == new:
            return "old_string and new_string are identical; nothing to do"
        return None

    async def execute(
        self, ctx: ToolContext, input: dict[str, Any]
    ) -> ToolResult:
        raw_path = input["path"]
        old = input["old_string"]
        new = input["new_string"]

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

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return ToolResult(
                content=f"Failed to read {p}: {e}",
                is_error=True,
                metadata={"path": str(p)},
            )

        count = content.count(old)
        if count == 0:
            return ToolResult(
                content=(
                    f"old_string not found in {p}. Your snapshot of the file may "
                    "be stale; re-read it with ReadFile before editing."
                ),
                is_error=True,
                metadata={"path": str(p), "match_count": 0},
            )
        if count > 1:
            return ToolResult(
                content=(
                    f"old_string appears {count} times in {p}. "
                    "Provide more surrounding context (extra lines above/below) "
                    "to make the match unique."
                ),
                is_error=True,
                metadata={"path": str(p), "match_count": count},
            )

        # Compute replacement.
        match_idx = content.index(old)
        new_content = content[:match_idx] + new + content[match_idx + len(old):]

        try:
            p.write_text(new_content, encoding="utf-8")
        except OSError as e:
            return ToolResult(
                content=f"Failed to write {p}: {e}",
                is_error=True,
                metadata={"path": str(p)},
            )

        # Build preview around the change.
        # Use the new content. Find which line the change starts on (1-based).
        change_line = new_content.count("\n", 0, match_idx) + 1
        # Replacement may span multiple lines; figure out where it ends.
        new_end_idx = match_idx + len(new)
        change_end_line = new_content.count("\n", 0, new_end_idx) + 1

        new_lines = new_content.splitlines()
        start = max(0, change_line - 1 - _PREVIEW_CONTEXT_LINES)
        end = min(len(new_lines), change_end_line + _PREVIEW_CONTEXT_LINES)
        preview_lines = [
            f"{i + 1}\t{new_lines[i]}" for i in range(start, end)
        ]
        preview = "\n".join(preview_lines)

        return ToolResult(
            content=(
                f"Edited {p}.\n\n"
                f"Preview (lines {start + 1}-{end}):\n{preview}"
            ),
            is_error=False,
            metadata={
                "path": str(p),
                "match_count": 1,
                "change_line": change_line,
                "change_end_line": change_end_line,
            },
        )
