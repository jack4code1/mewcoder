import asyncio
import json
from dataclasses import dataclass
from typing import Any

from .adapter import McpToolAdapter


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    command: list[str]
    enabled: bool = True
    timeout_seconds: float = 30


class StdioMcpClient:
    """Minimal newline-delimited JSON-RPC client for an MCP stdio server."""

    def __init__(self, config: McpServerConfig) -> None:
        self.config = config
        self.process: asyncio.subprocess.Process | None = None
        self._request_id = 0

    async def start(self) -> None:
        if self.process is not None:
            return
        self.process = await asyncio.create_subprocess_exec(
            *self.config.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await self.request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "mewcode", "version": "0.1.0"},
        })
        await self.notify("notifications/initialized")

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if self.process is None or self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("MCP server is not started")
        self._request_id += 1
        request_id = self._request_id
        await self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        while True:
            line = await asyncio.wait_for(self.process.stdout.readline(), self.config.timeout_seconds)
            if not line:
                raise RuntimeError("MCP server closed stdout")
            response = json.loads(line.decode("utf-8"))
            if response.get("id") == request_id:
                if "error" in response:
                    raise RuntimeError(str(response["error"]))
                return response.get("result")

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def _write(self, message: dict[str, Any]) -> None:
        assert self.process is not None and self.process.stdin is not None
        self.process.stdin.write((json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self.request("tools/list")
        return list((result or {}).get("tools", []))

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return await self.request("tools/call", {"name": name, "arguments": arguments})

    async def close(self) -> None:
        if self.process is None:
            return
        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 2)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        self.process = None


class McpServerManager:
    def __init__(self, servers: list[McpServerConfig] | None = None) -> None:
        self.servers = {server.name: server for server in servers or []}
        self.status = {name: "disabled" if not server.enabled else "configured" for name, server in self.servers.items()}
        self.clients: dict[str, StdioMcpClient] = {}

    def disable(self, name: str) -> None:
        if name in self.status:
            self.status[name] = "disabled"

    def register_tools(self, name: str, tools: list[object], registry) -> int:
        """Expose discovered adapters only for an enabled, configured server."""
        if self.status.get(name) != "configured":
            return 0
        count = 0
        for tool in tools:
            registry.register(tool)
            count += 1
        self.status[name] = "ready"
        return count

    async def connect_and_register(self, name: str, registry) -> int:
        config = self.servers.get(name)
        if config is None or self.status.get(name) != "configured":
            return 0
        client = StdioMcpClient(config)
        await client.start()
        tools = []
        for item in await client.list_tools():
            raw_name = str(item["name"])
            tools.append(McpToolAdapter(
                f"mcp__{name}__{raw_name}", str(item.get("description", "")),
                item.get("inputSchema", {"type": "object"}), name,
                lambda arguments, raw_name=raw_name: client.call_tool(raw_name, arguments),
            ))
        self.clients[name] = client
        return self.register_tools(name, tools, registry)

    async def close(self) -> None:
        await asyncio.gather(*(client.close() for client in self.clients.values()))
        self.clients.clear()
