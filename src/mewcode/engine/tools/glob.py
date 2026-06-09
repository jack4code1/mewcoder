"""Glob tool: find files by pattern, sorted by mtime descending.

Excludes common noisy directories. Capped at MAX_RESULTS files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .base import Tool, ToolContext, ToolResult


EXCLUDE_DIRS: frozenset[str] = frozenset({
    ".git",
    "node_modules",
    "vendor",
    "__pycache__",
    ".idea",
    ".venv",
    "venv",
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
})

_MAX_RESULTS = 200


class GlobTool(Tool):
    name = "Glob"
    description = (
        "Find files by glob pattern.\n"
        "WHEN TO USE: Locating files when you know the name or extension. Pair "
        "with ReadFile/Grep afterwards.\n"
        "WHEN NOT TO USE: Searching file CONTENTS — that's Grep.\n"
        "PATTERN: Standard glob with `**` for recursive descent. Examples: "
        "`**/*.py`, `src/**/test_*.py`, `*.md`.\n"
        "EXCLUDED DIRECTORIES (always skipped): "
        f"{', '.join(sorted(EXCLUDE_DIRS))}.\n"
        f"RESULT FORMAT: One relative path per line, sorted by modification time "
        f"DESCENDING (most recently changed first). Capped at {_MAX_RESULTS} "
        "results — refine the pattern if you hit the cap."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern, supports `**`. Example: `**/*.py`.",
            },
            "path": {
                "type": "string",
                "description": "Search root (absolute or relative to working directory). "
                               "Defaults to the working directory.",
            },
        },
        "required": ["pattern"],
        "additionalProperties": False,
    }
    category = "search"
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True

    def validate_input(self, input: dict[str, Any]) -> Optional[str]:
        pattern = input.get("pattern")
        if not isinstance(pattern, str) or not pattern.strip():
            return "pattern is required and must be a non-empty string"
        path = input.get("path")
        if path is not None and (not isinstance(path, str) or not path.strip()):
            return "path, when provided, must be a non-empty string"
        return None

    async def execute(
        self, ctx: ToolContext, input: dict[str, Any]
    ) -> ToolResult:
        pattern = input["pattern"]
        raw_root = input.get("path") or "."

        try:
            root = ctx.resolve_path(raw_root)
        except Exception as e:  # noqa: BLE001
            return ToolResult(
                content=f"Invalid path {raw_root!r}: {e}",
                is_error=True,
                metadata={"path": raw_root},
            )

        if not root.exists() or not root.is_dir():
            return ToolResult(
                content=f"Search root is not a directory: {root}",
                is_error=True,
                metadata={"path": str(root)},
            )

        try:
            iterator = root.glob(pattern)
        except (ValueError, OSError) as e:
            return ToolResult(
                content=f"Invalid glob pattern {pattern!r}: {e}",
                is_error=True,
                metadata={"pattern": pattern},
            )

        matches: list[tuple[float, Path]] = []
        try:
            for p in iterator:
                # Skip if any path part is in EXCLUDE_DIRS.
                if any(part in EXCLUDE_DIRS for part in p.parts):
                    continue
                if not p.is_file():
                    continue
                try:
                    mtime = p.stat().st_mtime
                except OSError:
                    mtime = 0.0
                matches.append((mtime, p))
        except OSError as e:
            return ToolResult(
                content=f"Failed while walking {root}: {e}",
                is_error=True,
                metadata={"path": str(root), "pattern": pattern},
            )

        matches.sort(key=lambda x: x[0], reverse=True)
        truncated = len(matches) > _MAX_RESULTS
        kept = matches[:_MAX_RESULTS]

        rel_lines: list[str] = []
        for _, p in kept:
            try:
                rel = p.relative_to(root)
            except ValueError:
                rel = p
            rel_lines.append(str(rel).replace("\\", "/"))

        if not rel_lines:
            body = f"(no files matched pattern {pattern!r} under {root})"
        else:
            body = "\n".join(rel_lines)
            if truncated:
                body += (
                    f"\n\n... [{len(matches) - _MAX_RESULTS} more matches omitted; "
                    "refine the pattern to narrow results] ..."
                )

        return ToolResult(
            content=body,
            is_error=False,
            metadata={
                "pattern": pattern,
                "root": str(root),
                "match_count": len(matches),
                "returned": len(kept),
                "truncated": truncated,
            },
        )
