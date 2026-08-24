"""Visible hook execution with explicit blocking semantics."""

from dataclasses import dataclass
from typing import Awaitable, Callable


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
