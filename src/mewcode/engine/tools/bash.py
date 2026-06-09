"""Bash tool: run a shell command in the working directory.

Stdout and stderr are merged. Output exceeding MAX_OUTPUT_CHARS is
truncated head + tail. Non-zero exit codes are returned as normal results
(is_error=False) so the model can diagnose; only timeouts are errors.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

from .base import Tool, ToolContext, ToolResult


_DEFAULT_TIMEOUT = 30
_MAX_TIMEOUT = 600
_MAX_OUTPUT_CHARS = 10000
_HEAD_KEEP = 2000
_TAIL_KEEP = 8000


def _truncate(text: str) -> tuple[str, bool]:
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text, False
    head = text[:_HEAD_KEEP]
    tail = text[-_TAIL_KEEP:]
    dropped = len(text) - _HEAD_KEEP - _TAIL_KEEP
    sep = f"\n\n... [{dropped} chars truncated] ...\n\n"
    return head + sep + tail, True


class BashTool(Tool):
    name = "Bash"
    description = (
        "Execute a shell command in the current working directory.\n"
        "WHEN TO USE: Running tests, builds, linters, git commands, system "
        "inspection, or anything that doesn't fit the file/search tools.\n"
        "WHEN NOT TO USE: Reading or editing files (use ReadFile/WriteFile/EditFile). "
        "Long-running interactive processes — there's no stdin and a hard timeout.\n"
        "STREAMS: stdout and stderr are merged into a single output stream.\n"
        f"TIMEOUT: default {_DEFAULT_TIMEOUT}s, max {_MAX_TIMEOUT}s. "
        "Set the `timeout` field for slow commands. Timeouts are reported as errors.\n"
        f"OUTPUT: capped at {_MAX_OUTPUT_CHARS} chars; the head ({_HEAD_KEEP}) and "
        f"tail ({_TAIL_KEEP}) are preserved with a `[N chars truncated]` marker between.\n"
        "EXIT CODE: a non-zero exit code is NOT an error of this tool — it's a "
        "diagnostic signal. The exit code is included in the response."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command line. Runs through the system default shell.",
            },
            "timeout": {
                "type": "integer",
                "minimum": 1,
                "maximum": _MAX_TIMEOUT,
                "description": f"Timeout in seconds (default {_DEFAULT_TIMEOUT}).",
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }
    category = "shell"
    is_read_only = False
    is_destructive = True
    is_concurrency_safe = False

    def validate_input(self, input: dict[str, Any]) -> Optional[str]:
        cmd = input.get("command")
        if not isinstance(cmd, str) or not cmd.strip():
            return "command is required and must be a non-empty string"
        timeout = input.get("timeout")
        if timeout is not None:
            if not isinstance(timeout, int) or timeout < 1 or timeout > _MAX_TIMEOUT:
                return f"timeout must be an integer between 1 and {_MAX_TIMEOUT}"
        return None

    async def execute(
        self, ctx: ToolContext, input: dict[str, Any]
    ) -> ToolResult:
        command = input["command"]
        timeout = input.get("timeout", _DEFAULT_TIMEOUT)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(ctx.working_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except OSError as e:
            return ToolResult(
                content=f"Failed to start command: {e}",
                is_error=True,
                metadata={"command": command},
            )

        try:
            stdout_bytes, _ = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            # Kill the process and drain.
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            try:
                await proc.wait()
            except Exception:  # noqa: BLE001
                pass
            return ToolResult(
                content=(
                    f"Command timed out after {timeout}s and was killed.\n"
                    f"Command: {command}"
                ),
                is_error=True,
                metadata={
                    "command": command,
                    "timeout": timeout,
                    "reason": "timeout",
                },
            )

        text = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        truncated_text, truncated = _truncate(text)
        exit_code = proc.returncode if proc.returncode is not None else -1

        body = (
            f"<bash_output exit_code={exit_code}>\n"
            f"{truncated_text}\n"
            "</bash_output>"
        )

        return ToolResult(
            content=body,
            is_error=False,
            metadata={
                "command": command,
                "exit_code": exit_code,
                "truncated": truncated,
                "raw_chars": len(text),
                "timeout": timeout,
            },
        )
