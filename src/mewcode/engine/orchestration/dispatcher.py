"""Deterministic workflow dispatch after a validated routing decision."""

from __future__ import annotations

from typing import Awaitable, Callable

from .routing import IntentDecision


Workflow = Callable[[str], Awaitable[None]]


class RouteDispatcher:
    def __init__(self, *, direct: Workflow, react: Workflow, plan_execute: Workflow, delegate: Workflow) -> None:
        self.workflows = {
            "direct": direct,
            "react": react,
            "plan_execute": plan_execute,
            "delegate": delegate,
        }

    async def dispatch(self, decision: IntentDecision, task: str) -> None:
        await self.workflows[decision.mode](task)
