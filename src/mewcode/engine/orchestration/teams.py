from dataclasses import dataclass, field
import asyncio
from typing import Awaitable, Callable

from .tasks import TaskRun, TaskSpec
from .tasks import TaskRunner


@dataclass
class TeamCoordinator:
    max_concurrency: int = 2
    runs: list[TaskRun] = field(default_factory=list)

    def submit(self, spec: TaskSpec) -> TaskRun:
        run = TaskRun(spec)
        self.runs.append(run)
        return run

    def conflicts(self, specs: list[TaskSpec]) -> list[str]:
        seen, conflicts = set(), []
        for spec in specs:
            for target in spec.context:
                if target in seen:
                    conflicts.append(target)
                seen.add(target)
        return conflicts

    def summary(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for run in self.runs:
            result[run.status] = result.get(run.status, 0) + 1
        return result

    async def run_all(
        self, specs: list[TaskSpec], worker: Callable[[TaskSpec], Awaitable[str]]
    ) -> list[TaskRun]:
        conflicts = self.conflicts(specs)
        if conflicts:
            raise ValueError(f"task context conflicts: {', '.join(conflicts)}")
        semaphore = asyncio.Semaphore(max(1, self.max_concurrency))
        runner = TaskRunner()

        async def run_one(spec: TaskSpec) -> TaskRun:
            async with semaphore:
                return await runner.run(spec, worker)

        runs = list(await asyncio.gather(*(run_one(spec) for spec in specs)))
        self.runs.extend(runs)
        return runs
