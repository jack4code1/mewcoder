"""Plan-and-execute primitives with bounded replanning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable
from uuid import uuid4


@dataclass
class PlanStep:
    objective: str
    id: str = field(default_factory=lambda: uuid4().hex[:8])
    status: str = "pending"
    result: str = ""
    error: str = ""


@dataclass
class ExecutionPlan:
    objective: str
    steps: list[PlanStep]
    replans: int = 0


Planner = Callable[[str, list[PlanStep]], Awaitable[list[PlanStep]]]
Executor = Callable[[PlanStep, list[PlanStep]], Awaitable[str]]


class PlanExecutor:
    """Execute a generated plan and ask the planner to recover from failures."""

    def __init__(self, max_replans: int = 1) -> None:
        self.max_replans = max(0, max_replans)

    async def run(self, objective: str, planner: Planner, executor: Executor) -> ExecutionPlan:
        plan = ExecutionPlan(objective, await planner(objective, []))
        index = 0
        while index < len(plan.steps):
            step = plan.steps[index]
            step.status = "running"
            try:
                step.result = await executor(step, plan.steps)
                step.status = "completed"
                index += 1
            except Exception as exc:  # execution failures are planner input
                step.status = "failed"
                step.error = str(exc)
                if plan.replans >= self.max_replans:
                    break
                plan.replans += 1
                completed = [item for item in plan.steps if item.status == "completed"]
                replacement = await planner(objective, plan.steps)
                plan.steps = completed + replacement
                index = len(completed)
        return plan
