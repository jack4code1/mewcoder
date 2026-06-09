"""Grep tool: regex search across files in the working tree.

Skips binary files and noisy directories. Optional `include` glob and
`context` lines (-A == -B). Capped at MAX_MATCHES total matches.
"""

from __future__ import annotations

import fnmatch
import re
from collections import deque
from pathlib import Path
from typing import Any, Optional

from .base import Tool, ToolContext, ToolResult
from .glob import EXCLUDE_DIRS


_MAX_MATCHES = 100
_BINARY_SNIFF_BYTES = 512
_MAX_CONTEXT = 10


class GrepTool(Tool):
    name = "Grep"
    description = (
        "Search file contents using a regular expression.\n"
        "WHEN TO USE: Finding where a symbol, string, or pattern appears across "
        "the codebase. Pair with ReadFile afterwards to read the surrounding code.\n"
        "WHEN NOT TO USE: Locating files by NAME (use Glob). Reading a known file "
        "(use ReadFile).\n"
        "PATTERN: Python `re` regex. Anchor and escape as needed. Examples: "
        "`def main\\b`, `class\\s+\\w+`, `TODO`.\n"
        "include: Optional glob (e.g. `*.py`, `**/*.ts`) to filter file names.\n"
        f"context: Optional integer 0-{_MAX_CONTEXT}; lines of context shown "
        "before AND after each match.\n"
        "EXCLUDED: binary files (sniffed) and noisy directories "
        f"({', '.join(sorted(EXCLUDE_DIRS))}).\n"
        f"OUTPUT FORMAT: `path:line: content` per match. Capped at {_MAX_MATCHES} "
        "total matches across all files. Refine the pattern or `include` if you "
        "hit the cap."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Python regex pattern.",
            },
            "path": {
                "type": "string",
                "description": "Search root (absolute or relative to working directory). "
                               "Defaults to the working directory.",
            },
            "include": {
                "type": "string",
                "description": "Optional glob applied to filenames (not full paths). "
                               "Example: `*.py`.",
            },
            "context": {
                "type": "integer",
                "minimum": 0,
                "maximum": _MAX_CONTEXT,
                "description": "Lines of context before AND after each match (0-10).",
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
        if not isinstance(pattern, str) or pattern == "":
            return "pattern is required and must be a non-empty string"
        try:
            re.compile(pattern)
        except re.error as e:
            return f"invalid regex: {e}"
        path = input.get("path")
        if path is not None and (not isinstance(path, str) or not path.strip()):
            return "path, when provided, must be a non-empty string"
        include = input.get("include")
        if include is not None and not isinstance(include, str):
            return "include must be a string glob"
        context = input.get("context")
        if context is not None:
            if not isinstance(context, int) or context < 0 or context > _MAX_CONTEXT:
                return f"context must be an integer between 0 and {_MAX_CONTEXT}"
        return None

    async def execute(
        self, ctx: ToolContext, input: dict[str, Any]
    ) -> ToolResult:
        pattern = input["pattern"]
        raw_root = input.get("path") or "."
        include = input.get("include")
        context = input.get("context", 0)

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(
                content=f"Invalid regex {pattern!r}: {e}",
                is_error=True,
                metadata={"pattern": pattern},
            )

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

        matches: list[str] = []
        files_scanned = 0
        truncated = False

        def emit(path_rel: str, line_no: int, line: str) -> None:
            matches.append(f"{path_rel}:{line_no}: {line.rstrip()}")

        for fpath in self._walk(root):
            if include and not fnmatch.fnmatch(fpath.name, include):
                continue
            if not self._is_text_file(fpath):
                continue
            files_scanned += 1

            try:
                with fpath.open("r", encoding="utf-8", errors="replace") as fh:
                    pre_buf: deque[tuple[int, str]] = deque(maxlen=context) if context else deque()
                    post_remaining = 0
                    last_emitted_line = -10**9

                    rel_str = str(fpath.relative_to(root)).replace("\\", "/")

                    for line_no, line in enumerate(fh, start=1):
                        line_stripped = line.rstrip("\n")
                        if regex.search(line_stripped):
                            # emit context-before (only those not already emitted)
                            if context:
                                for ctx_no, ctx_line in pre_buf:
                                    if ctx_no > last_emitted_line:
                                        emit(rel_str, ctx_no, ctx_line)
                            emit(rel_str, line_no, line_stripped)
                            last_emitted_line = line_no
                            post_remaining = context
                            if len(matches) >= _MAX_MATCHES:
                                truncated = True
                                break
                        else:
                            if post_remaining > 0:
                                emit(rel_str, line_no, line_stripped)
                                last_emitted_line = line_no
                                post_remaining -= 1
                                if len(matches) >= _MAX_MATCHES:
                                    truncated = True
                                    break

                        if context:
                            pre_buf.append((line_no, line_stripped))
            except OSError:
                continue

            if truncated:
                break

        if not matches:
            body = f"(no matches for pattern {pattern!r} under {root})"
        else:
            body = "\n".join(matches)
            if truncated:
                body += (
                    f"\n\n... [match cap of {_MAX_MATCHES} hit; refine the pattern "
                    "or use `include` to narrow] ..."
                )

        return ToolResult(
            content=body,
            is_error=False,
            metadata={
                "pattern": pattern,
                "root": str(root),
                "match_count": len(matches),
                "files_scanned": files_scanned,
                "truncated": truncated,
                "context": context,
                "include": include,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _walk(self, root: Path):
        """Yield files under root, skipping EXCLUDE_DIRS at any depth."""
        # Use os.walk-style iteration via pathlib for cross-platform behaviour.
        import os

        for dirpath, dirnames, filenames in os.walk(root):
            # Prune excluded directories in-place so os.walk doesn't descend.
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            base = Path(dirpath)
            for name in filenames:
                yield base / name

    def _is_text_file(self, path: Path) -> bool:
        try:
            with path.open("rb") as fh:
                head = fh.read(_BINARY_SNIFF_BYTES)
        except OSError:
            return False
        if not head:
            return True
        if b"\x00" in head:
            return False
        return True
