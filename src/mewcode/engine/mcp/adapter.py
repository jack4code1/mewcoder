"""Adapter for exposing remote MCP callables through the normal tool boundary."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from ..security.models import OperationKind, RiskLevel
from ..tools.base import Tool, ToolContext, ToolResult


class McpToolAdapter(Tool):
    def __init__(self, name: str, description: str, schema: dict[str, Any], server: str,
                 invoke: Callable[[dict[str, Any]], Awaitable[Any]]) -> None:
        self.name, self.description, self.input_schema = name, description, schema
        self.server, self._invoke = server, invoke
        self.operation_kind, self.risk_level = OperationKind.EXTERNAL, RiskLevel.HIGH
        self.is_read_only = False

    async def execute(self, ctx: ToolContext, input: dict[str, Any]) -> ToolResult:
        try:
            value = await self._invoke(input)
            return ToolResult(str(value), metadata={"server": self.server})
        except Exception as exc:
            return ToolResult(f"MCP tool {self.name} failed: {exc}", True, {"server": self.server})
