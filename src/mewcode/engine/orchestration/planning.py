"""Plan-and-execute primitives with bounded replanning."""

from __future__ import annotations

from dataclasses import dataclass, field
import asyncio
from enum import Enum
import json
from fnmatch import fnmatchcase
from typing import Awaitable, Callable
from uuid import uuid4

from .tool_policy import ROLE_TOOL_POLICY


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


@dataclass
class PlanTask:
    id: str
    description: str
    role: str
    depends_on: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    status: str = "pending"
    result: str = ""
    error: str = ""
    attempts: int = 0


@dataclass
class TaskPlan:
    objective: str
    tasks: list[PlanTask]
    outcome: str = "pending"
    failed_task_id: str | None = None

    def summary(self) -> str:
        return "\n".join(f"[{task.id}] {task.role} {task.status}: {task.description}" for task in self.tasks)


def parse_task_plan(raw: str, objective: str, available_tools: set[str]) -> TaskPlan:
    """Validate structured planner JSON before building a task dependency graph."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(text)
    items = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError("planner response requires a non-empty tasks array")
    tasks: list[PlanTask] = []
    ids = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each planned task must be an object")
        task_id, description, role = item.get("id"), item.get("description"), item.get("role")
        depends_on, files, tools = item.get("depends_on", []), item.get("files", []), item.get("allowed_tools", [])
        if not all(isinstance(value, str) and value.strip() for value in (task_id, description, role)) or task_id in ids:
            raise ValueError("tasks require unique id, description, and role")
        if not all(isinstance(value, str) for value in depends_on + files + tools):
            raise ValueError("task dependencies, files, and tools must be string lists")
        unknown = set(tools) - available_tools
        if unknown:
            raise ValueError(f"task {task_id} requests unavailable tools: {', '.join(sorted(unknown))}")
        ids.add(task_id)
        tasks.append(PlanTask(task_id, description, role, depends_on, files, tools))
    for task in tasks:
        if task.id in task.depends_on or not set(task.depends_on) <= ids:
            raise ValueError(f"task {task.id} has invalid dependencies")
    _validate_acyclic(tasks)
    for task in tasks:
        role_tools = ROLE_TOOL_POLICY.get(task.role.casefold())
        if role_tools is None:
            raise ValueError(f"task {task.id} has an unknown role: {task.role}")
        excess = set(task.allowed_tools) - role_tools
        if excess:
            raise ValueError(
                f"task {task.id} requests tools outside role policy: {', '.join(sorted(excess))}"
            )
    return TaskPlan(objective, tasks)


def _validate_acyclic(tasks: list[PlanTask]) -> None:
    graph = {task.id: task.depends_on for task in tasks}
    visiting, visited = set(), set()
    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise ValueError("task dependency graph contains a cycle")
        if task_id not in visited:
            visiting.add(task_id)
            for dependency in graph[task_id]:
                visit(dependency)
            visiting.remove(task_id)
            visited.add(task_id)
    for task in tasks:
        visit(task.id)


TaskWorker = Callable[[PlanTask, TaskPlan], Awaitable[str]]


class TaskFailureAction(str, Enum):
    """The scheduler-owned decision to make after a task failure."""

    BLOCK_DOWNSTREAM = "block_downstream"
    RETRY = "retry"
    REPLAN = "replan"
    STOP = "stop"


TaskFailurePolicy = Callable[[PlanTask, TaskPlan], TaskFailureAction]


class TaskScheduler:
    """Run dependency-ready tasks with scheduler-owned failure transitions."""

    def __init__(
        self,
        max_concurrency: int = 2,
        failure_policy: TaskFailurePolicy | None = None,
        max_task_retries: int = 0,
    ) -> None:
        self.max_concurrency = max(1, max_concurrency)
        self.failure_policy = failure_policy or (lambda _task, _plan: TaskFailureAction.BLOCK_DOWNSTREAM)
        self.max_task_retries = max(0, max_task_retries)

    async def run(self, plan: TaskPlan, worker: TaskWorker) -> TaskPlan:
        while True:
            completed = {task.id for task in plan.tasks if task.status == "completed"}
            ready = [task for task in plan.tasks if task.status == "pending" and set(task.depends_on) <= completed]
            if not ready:
                break
            batch = self._non_conflicting_batch(ready)
            failed_in_batch: list[PlanTask] = []

            async def run_one(task: PlanTask) -> None:
                task.status = "running"
                task.attempts += 1
                try:
                    task.result = await worker(task, plan)
                    task.status = "completed"
                except Exception as exc:
                    task.status, task.error = "failed", str(exc)
                    failed_in_batch.append(task)
            await asyncio.gather(*(run_one(task) for task in batch))

            for task in failed_in_batch:
                action = self.failure_policy(task, plan)
                plan.failed_task_id = task.id
                if action is TaskFailureAction.RETRY and task.attempts <= self.max_task_retries:
                    task.status = "pending"
                    continue
                if action is TaskFailureAction.REPLAN:
                    plan.outcome = "replan_required"
                    self._block_pending(plan)
                    return plan
                if action is TaskFailureAction.STOP:
                    plan.outcome = "stopped"
                    self._block_pending(plan)
                    return plan
        for task in plan.tasks:
            if task.status == "pending":
                task.status = "blocked"
        plan.outcome = "completed" if all(task.status == "completed" for task in plan.tasks) else "failed"
        return plan

    @staticmethod
    def _block_pending(plan: TaskPlan) -> None:
        for task in plan.tasks:
            if task.status == "pending":
                task.status = "blocked"

    def _non_conflicting_batch(self, ready: list[PlanTask]) -> list[PlanTask]:
        """Select ready tasks whose declared workspace resources do not overlap.

        An empty ``files`` declaration is deliberately treated as an unknown
        write set.  It must run alone: allowing it to overlap would make an
        incomplete plan silently bypass the scheduler's conflict protection.
        """
        batch: list[PlanTask] = []
        for task in ready:
            if not any(self._tasks_conflict(task, scheduled) for scheduled in batch):
                batch.append(task)
            if len(batch) >= self.max_concurrency:
                break
        return batch

    @staticmethod
    def _tasks_conflict(left: PlanTask, right: PlanTask) -> bool:
        if not left.files or not right.files:
            return True
        return any(
            TaskScheduler._paths_conflict(left_path, right_path)
            for left_path in left.files
            for right_path in right.files
        )

    @staticmethod
    def _paths_conflict(left: str, right: str) -> bool:
        """Conservatively detect equal, nested, and glob-overlapping paths."""
        left = left.strip().lstrip("./").rstrip("/")
        right = right.strip().lstrip("./").rstrip("/")
        if not left or not right:
            return True
        if left == right or left.startswith(f"{right}/") or right.startswith(f"{left}/"):
            return True

        left_glob = any(char in left for char in "*?[")
        right_glob = any(char in right for char in "*?[")
        if left_glob and fnmatchcase(right, left):
            return True
        if right_glob and fnmatchcase(left, right):
            return True

        # Two patterns cannot always be intersected exactly. Compare their
        # non-pattern prefixes and serialize when either pattern can cover the
        # other's subtree (for example, ``src/**/*.py`` and ``src/app.py``).
        if left_glob or right_glob:
            left_prefix = left.split("*", 1)[0].split("?", 1)[0].split("[", 1)[0].rstrip("/")
            right_prefix = right.split("*", 1)[0].split("?", 1)[0].split("[", 1)[0].rstrip("/")
            return (
                not left_prefix
                or not right_prefix
                or left_prefix == right_prefix
                or left_prefix.startswith(f"{right_prefix}/")
                or right_prefix.startswith(f"{left_prefix}/")
            )
        return False
