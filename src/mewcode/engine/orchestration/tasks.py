from dataclasses import dataclass, field
from typing import Awaitable, Callable, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from .worktrees import WorktreeLease, WorktreeManager


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
    diff: str = ""
    worktree_path: str | None = None

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

    async def run_isolated(
        self,
        spec: TaskSpec,
        worktrees: "WorktreeManager",
        worker: Callable[[TaskSpec, "WorktreeLease"], Awaitable[str]],
        keep_worktree: bool = False,
    ) -> TaskRun:
        """Run one task in a disposable clean worktree and preserve its diff."""
        run = TaskRun(spec, status="running")
        lease = None
        try:
            lease = worktrees.create(run.id)
            run.worktree_path = str(lease.path)
            run.result = await worker(spec, lease)
            run.diff = worktrees.diff(run.id)
            if run.status != "cancelled":
                run.status = "completed"
        except Exception as exc:
            run.status, run.result = "failed", str(exc)
        finally:
            if lease is not None and not keep_worktree:
                worktrees.cleanup(run.id)
        return run
