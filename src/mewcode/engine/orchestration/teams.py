from dataclasses import dataclass, field

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
