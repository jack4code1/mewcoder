"""Visible hook execution with explicit blocking semantics."""

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

import yaml

from ..security.models import ExecutionRequest, OperationKind, RiskLevel


@dataclass(frozen=True)
class HookDefinition:
    event: str
    name: str
    blocking: bool = False


@dataclass(frozen=True)
class HookResult:
    name: str
    success: bool
    message: str = ""


class HookRunner:
    def __init__(self) -> None:
        self._handlers: dict[str, list[tuple[HookDefinition, Callable[[], Awaitable[None]]]]] = {}

    def register(self, definition: HookDefinition, handler: Callable[[], Awaitable[None]]) -> None:
        self._handlers.setdefault(definition.event, []).append((definition, handler))

    async def run(self, event: str) -> list[HookResult]:
        results = []
        for definition, handler in self._handlers.get(event, []):
            try:
                await handler()
                results.append(HookResult(definition.name, True))
            except Exception as exc:
                results.append(HookResult(definition.name, False, str(exc)))
                if definition.blocking:
                    break
        return results


class ProjectHookStore:
    """Load opt-in project hooks that always use the execution gateway."""

    def __init__(self, workspace: Path) -> None:
        self.path = workspace.resolve() / ".mewcode" / "hooks.yaml"

    def definitions(self) -> list[tuple[HookDefinition, str]]:
        if not self.path.exists():
            return []
        raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        result = []
        for item in raw.get("hooks", []):
            if not isinstance(item, dict) or not all(key in item for key in ("event", "name", "command")):
                continue
            result.append((HookDefinition(str(item["event"]), str(item["name"]), bool(item.get("blocking", True))), str(item["command"])))
        return result

    def build_runner(self, gateway) -> HookRunner:
        runner = HookRunner()
        for definition, command in self.definitions():
            async def handler(command=command):
                result = await gateway.execute(ExecutionRequest(
                    "Bash", {"command": command}, source="hook",
                    operation=OperationKind.COMMAND, risk=RiskLevel.HIGH,
                ))
                if result.is_error:
                    raise RuntimeError(result.content)
            runner.register(definition, handler)
        return runner
