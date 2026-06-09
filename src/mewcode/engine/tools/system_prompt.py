"""Build the English system prompt that primes the model for tool use.

Output is appended (as a system message) at the head of every chat
request — see plan §模块设计 / §模块交互. Content is intentionally short:
the actual tool descriptions travel in the `tools` parameter, so the
system prompt only needs cwd / OS / orientation guidelines and the
language policy.
"""

from __future__ import annotations

from .base import ToolContext
from .registry import ToolRegistry


def build_system_prompt(ctx: ToolContext, registry: ToolRegistry) -> str:
    enabled_names = [t.name for t in registry.list_enabled()]
    if enabled_names:
        tools_line = (
            "Available tools: " + ", ".join(enabled_names) + "."
        )
    else:
        tools_line = "No tools are currently enabled."

    return (
        "You are MewCode, an autonomous coding assistant.\n"
        "\n"
        f"Working directory: {ctx.working_dir}\n"
        f"Host OS: {ctx.os_name}\n"
        f"{tools_line}\n"
        "\n"
        "Tool usage guidelines:\n"
        "- Use Grep or Glob to locate code before reading files.\n"
        "- For EditFile, include enough surrounding context in old_string to make "
        "the match unique within the file.\n"
        "- Bash output merges stdout and stderr and is truncated when very long; "
        "do not rely on full output for chatty commands.\n"
        "- Paths can be absolute or relative to the working directory.\n"
        "- Treat tool results that are marked as errors as recoverable feedback: "
        "adjust your inputs or try a different approach.\n"
        "\n"
        "Language policy: think and call tools in English. "
        "Reply to the user in Chinese."
    )
