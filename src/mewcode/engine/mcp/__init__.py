"""Minimal isolated MCP server configuration and status registry."""

from .manager import McpServerConfig, McpServerManager
from .adapter import McpToolAdapter
__all__ = ["McpServerConfig", "McpServerManager", "McpToolAdapter"]
