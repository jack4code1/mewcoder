from dataclasses import dataclass


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    command: list[str]
    enabled: bool = True
    timeout_seconds: float = 30


class McpServerManager:
    def __init__(self, servers: list[McpServerConfig] | None = None) -> None:
        self.servers = {server.name: server for server in servers or []}
        self.status = {name: "disabled" if not server.enabled else "configured" for name, server in self.servers.items()}

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
