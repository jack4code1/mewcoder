"""Tool registry: registration, enable/disable strategy, protocol formatting,
and execution dispatch with error containment.

The registry is the single integration point between the app/UI layer and
the tool subsystem. It hides protocol details from the upper layers.
"""

from __future__ import annotations

import time
from typing import Any, Optional, Union

from ...logger import logger
from .base import Tool, ToolContext, ToolError, ToolResult


EnableSpec = Union[str, list[str]]


class ToolRegistry:
    """Holds Tool instances and dispatches executions.

    Responsibilities:
      - Register Tool instances and prevent duplicates.
      - Maintain an "enabled" subset (selected at startup from config).
      - Expose the enabled subset in OpenAI / Anthropic tools-API formats.
      - Execute tools with error containment (recoverable errors become
        ToolResult(is_error=True); ToolError propagates; everything else
        is wrapped).
    """

    def __init__(self, ctx: ToolContext):
        self.ctx = ctx
        self._tools: dict[str, Tool] = {}
        self._enabled: set[str] = set()

    # ------------------------------------------------------------------
    # Registration / enable selection
    # ------------------------------------------------------------------

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("Tool.name must be non-empty")
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} already registered")
        self._tools[tool.name] = tool
        # Default: every newly registered tool is enabled. enable() may
        # narrow the set afterwards.
        self._enabled.add(tool.name)

    def enable(self, spec: EnableSpec) -> None:
        """Apply an enable strategy.

        Accepted forms:
          - "all": enable every registered tool.
          - "readonly": enable only tools with is_read_only=True.
          - list[str]: enable exactly the named tools (unknown names are
            ignored with a warning).
        """
        if spec == "all" or spec is None:
            self._enabled = set(self._tools.keys())
            return
        if spec == "readonly":
            self._enabled = {
                n for n, t in self._tools.items() if t.is_read_only
            }
            return
        if isinstance(spec, (list, tuple, set)):
            wanted = set(spec)
            unknown = wanted - set(self._tools.keys())
            for name in unknown:
                logger.warning("Tool %r requested in config but not registered", name)
            self._enabled = wanted & set(self._tools.keys())
            return
        raise ValueError(
            f"Unsupported enable spec: {spec!r} (use 'all', 'readonly', or list)"
        )

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[Tool]:
        if name not in self._enabled:
            return None
        return self._tools.get(name)

    def list_enabled(self) -> list[Tool]:
        return [self._tools[n] for n in self._tools if n in self._enabled]

    # ------------------------------------------------------------------
    # Protocol formatting
    # ------------------------------------------------------------------

    def to_openai_format(self) -> list[dict[str, Any]]:
        """Format enabled tools for the OpenAI Chat Completions `tools` field."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in self.list_enabled()
        ]

    def to_anthropic_format(self) -> list[dict[str, Any]]:
        """Format enabled tools for the Anthropic Messages `tools` field."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self.list_enabled()
        ]

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def execute(self, name: str, input: dict[str, Any]) -> ToolResult:
        """Dispatch a tool call. Always returns a ToolResult.

        Failure modes:
          - Unknown / disabled tool:    ToolResult(is_error=True, ...)
          - validate_input returned err: ToolResult(is_error=True, ...)
          - tool.execute raised ToolError: re-raised (system-level).
          - tool.execute raised anything else: wrapped into ToolResult(is_error).
        """
        tool = self._tools.get(name)
        if tool is None or name not in self._enabled:
            logger.info("Tool dispatch failed: %r not registered/enabled", name)
            return ToolResult(
                content=f"Tool '{name}' is not registered or is disabled.",
                is_error=True,
                metadata={"tool": name, "reason": "not_registered"},
            )

        err = tool.validate_input(input)
        if err is not None:
            logger.info("Tool %r input validation failed: %s", name, err)
            return ToolResult(
                content=f"Invalid input for {name}: {err}",
                is_error=True,
                metadata={"tool": name, "reason": "invalid_input"},
            )

        start = time.monotonic()
        try:
            result = await tool.execute(self.ctx, input)
        except ToolError:
            # System-level: propagate. Caller decides what to do.
            raise
        except Exception as e:  # noqa: BLE001  intentional broad catch
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception("Tool %r raised unexpectedly", name)
            return ToolResult(
                content=f"Tool {name} failed: {e.__class__.__name__}: {e}",
                is_error=True,
                metadata={
                    "tool": name,
                    "reason": "exception",
                    "duration_ms": duration_ms,
                },
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        # Annotate metadata with telemetry for the UI.
        if isinstance(result.metadata, dict):
            result.metadata.setdefault("tool", name)
            result.metadata.setdefault("duration_ms", duration_ms)
        logger.info(
            "Tool %r executed in %d ms (is_error=%s)",
            name,
            duration_ms,
            result.is_error,
        )
        return result
