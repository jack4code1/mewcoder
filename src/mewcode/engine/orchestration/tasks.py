from dataclasses import dataclass, field
from typing import Awaitable, Callable
from uuid import uuid4


@dataclass(frozen=True)
class TaskSpec:
    objective: str
    context: list[str] = field(default_factory=list)
    max_permissions: set[str] = field(default_factory=set)


@dataclass
class TaskRun:
    spec: TaskSpec
    id: str = field(default_factory=lambda: uuid4().hex)
    status: str = "pending"
    result: str = ""

    def cancel(self) -> None:
        self.status = "cancelled"


class TaskRunner:
    """Runs projected tasks without granting privileges beyond TaskSpec."""

    async def run(self, spec: TaskSpec, worker: Callable[[TaskSpec], Awaitable[str]]) -> TaskRun:
        run = TaskRun(spec, status="running")
        try:
            run.result = await worker(spec)
            if run.status != "cancelled":
                run.status = "completed"
        except Exception as exc:
            run.status, run.result = "failed", str(exc)
        return run
