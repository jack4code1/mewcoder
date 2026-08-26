"""Git-worktree execution for safe bounded parallel write tasks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from .collaboration import SharedTaskBoard, StructuredTaskScheduler
from .runtime import AgentMessage, AgentTask, InMemoryMessageBus, MessageType, TaskGraph, TaskStatus
from .worktrees import WorktreeLease, WorktreeManager


@dataclass
class IsolatedTaskRun:
    task_id: str
    worktree_path: str | None = None
    diff: str = ""
    applied: bool = False
    error: str = ""


IsolatedWorker = Callable[[AgentTask, dict, WorktreeLease | None], Awaitable[tuple[str, list[str]]]]


class WorktreeTaskScheduler(StructuredTaskScheduler):
    """Schedule write-capable tasks in Git worktrees and retain reviewable diffs."""

    def __init__(self, graph: TaskGraph, board: SharedTaskBoard, bus: InMemoryMessageBus, worktrees: WorktreeManager, max_concurrency: int = 2) -> None:
        super().__init__(graph, board, bus, max_concurrency)
        self.worktrees = worktrees
        self.runs: dict[str, IsolatedTaskRun] = {}

    async def run(self, worker: IsolatedWorker, cancel_event: asyncio.Event | None = None) -> None:  # type: ignore[override]
        while True:
            ready = self.graph.refresh_ready()
            if not ready:
                return
            batch = self._select_batch(ready, cancel_event)
            if not batch:
                return

            async def run_one(task: AgentTask) -> None:
                task.transition(TaskStatus.RUNNING)
                self.board.record("task_started", task_id=task.task_id, role=task.role)
                lease: WorktreeLease | None = None
                try:
                    if not self._is_read_only(task):
                        lease = self.worktrees.create(task.task_id)
                        self.runs[task.task_id] = IsolatedTaskRun(task.task_id, str(lease.path))
                        self.board.record("worktree_created", task_id=task.task_id, path=str(lease.path))
                    summary, artifacts = await worker(task, self.board.view_for(task.role, task.task_id), lease)
                    if lease is not None:
                        run = self.runs[task.task_id]
                        run.diff = self.worktrees.diff(task.task_id)
                        diff_ref = f"diff:{task.task_id}"
                        self.board.artifacts[diff_ref] = {"kind": "git_diff", "task_id": task.task_id, "worktree": str(lease.path), "content": run.diff}
                        artifacts = [*artifacts, diff_ref]
                    task.result_summary, task.artifact_refs = summary, artifacts
                    task.transition(TaskStatus.COMPLETED)
                    self.bus.send(AgentMessage("supervisor", task.role, MessageType.TASK_RESULT, task.task_id, {"summary": summary}, artifacts))
                    self.board.record("task_completed", task_id=task.task_id, role=task.role)
                except asyncio.CancelledError:
                    if task.status is TaskStatus.RUNNING:
                        task.transition(TaskStatus.CANCELLED)
                    self.board.record("task_cancelled", task_id=task.task_id)
                except Exception as exc:
                    task.error = str(exc)
                    run = self.runs.setdefault(task.task_id, IsolatedTaskRun(task.task_id))
                    run.error = task.error
                    if task.retry_count < task.max_retries:
                        task.retry_count += 1
                        task.transition(TaskStatus.FAILED)
                        task.transition(TaskStatus.READY)
                        self._cleanup_failed(task.task_id)
                        self.board.record("task_retry", task_id=task.task_id, retry=task.retry_count)
                    else:
                        task.transition(TaskStatus.FAILED)
                        self.board.record("task_failed", task_id=task.task_id, error=task.error)
            await asyncio.gather(*(run_one(task) for task in batch))

    def _select_batch(self, ready: list[AgentTask], cancel_event: asyncio.Event | None) -> list[AgentTask]:
        batch: list[AgentTask] = []
        for task in ready:
            if cancel_event is not None and cancel_event.is_set():
                task.transition(TaskStatus.CANCELLED)
                continue
            if any(self._files_conflict(task, other) for other in batch):
                continue
            batch.append(task)
            if len(batch) >= self.max_concurrency:
                break
        return batch or ready[:1]

    def apply(self, task_id: str) -> str:
        """Apply one completed, reviewed isolated diff to the clean main tree."""
        run = self.runs.get(task_id)
        task = self.graph.tasks.get(task_id)
        if run is None or task is None or not run.worktree_path:
            raise ValueError("task has no isolated worktree")
        if task.status is not TaskStatus.COMPLETED:
            raise RuntimeError("only completed task diffs can be applied")
        diff = self.worktrees.apply(task_id)
        run.applied = True
        self.board.record("worktree_applied", task_id=task_id)
        return diff

    def discard(self, task_id: str) -> None:
        if task_id in self.worktrees.leases:
            self.worktrees.cleanup(task_id)
        self.runs.pop(task_id, None)
        self.board.record("worktree_discarded", task_id=task_id)

    def _cleanup_failed(self, task_id: str) -> None:
        if task_id in self.worktrees.leases:
            self.worktrees.cleanup(task_id)
