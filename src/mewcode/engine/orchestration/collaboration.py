"""Shared-board collaboration for independently prompted agent roles."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from uuid import uuid4

from .runtime import AgentMessage, AgentTask, InMemoryMessageBus, MessageType, TaskGraph, TaskStatus, TraceEvent, parse_review_decision
from .tool_policy import ROLE_TOOL_POLICY


@dataclass(frozen=True)
class AgentAssignment:
    role: str
    objective: str


@dataclass
class BoardEntry:
    role: str
    objective: str
    task_id: str = ""
    result: str = ""
    status: str = "pending"


@dataclass
class SharedTaskBoard:
    objective: str
    entries: list[BoardEntry] = field(default_factory=list)
    review: str = ""
    verification: str = ""
    review_history: list[str] = field(default_factory=list)
    outcome: str = "pending"
    run_id: str = field(default_factory=lambda: f"run_{uuid4().hex[:12]}")
    tasks: dict[str, AgentTask] = field(default_factory=dict)
    artifacts: dict[str, dict] = field(default_factory=dict)
    messages: list[AgentMessage] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)

    def add_task(self, task: AgentTask) -> None:
        self.tasks[task.task_id] = task
        self.record("task_created", task_id=task.task_id, role=task.role)

    def record(self, kind: str, *, task_id: str | None = None, agent_id: str | None = None, **detail) -> None:
        self.trace.append(TraceEvent(kind, self.run_id, task_id, agent_id, detail))

    def add_message(self, message: AgentMessage) -> None:
        self.messages.append(message)
        self.record("message", task_id=message.task_id, agent_id=message.sender, type=message.type.value)

    def view_for(self, agent_id: str, task_id: str) -> dict:
        """Return only current-task inputs, dependency results, and addressed messages."""
        task = self.tasks[task_id]
        dependencies = [self.tasks[item] for item in task.depends_on]
        visible_messages = [
            item for item in self.messages
            if item.task_id == task_id and item.receiver in {agent_id, task.role}
        ]
        return {
            "run_id": self.run_id,
            "task": {
                "task_id": task.task_id, "goal": task.goal, "role": task.role,
                "files": task.files, "input_artifacts": task.input_artifacts,
            },
            "dependencies": [
                {"task_id": item.task_id, "summary": item.result_summary, "artifacts": item.artifact_refs}
                for item in dependencies
            ],
            "messages": [
                {"type": item.type.value, "content": item.content, "artifact_refs": item.artifact_refs}
                for item in visible_messages
            ],
            "artifacts": {key: self.artifacts[key] for key in task.input_artifacts if key in self.artifacts},
        }

    def summary(self) -> str:
        return "\n".join(
            f"[{entry.role}] {entry.objective}: {entry.result}" for entry in self.entries
        )


StructuredWorker = Callable[[AgentTask, dict], Awaitable[tuple[str, list[str]]]]


class StructuredTaskScheduler:
    """Task-DAG scheduler for a shared workspace.

    Only read-only roles may run concurrently.  Write-capable work remains
    serial unless a caller supplies isolated worktrees through its worker.
    """

    def __init__(self, graph: TaskGraph, board: SharedTaskBoard, bus: InMemoryMessageBus, max_concurrency: int = 2) -> None:
        self.graph, self.board, self.bus = graph, board, bus
        self.max_concurrency = max(1, max_concurrency)

    @staticmethod
    def _is_read_only(task: AgentTask) -> bool:
        return not ({"WriteFile", "EditFile", "Bash"} & set(task.allowed_tools))

    async def run(self, worker: StructuredWorker, cancel_event: asyncio.Event | None = None) -> None:
        while True:
            ready = self.graph.refresh_ready()
            if not ready:
                return
            batch: list[AgentTask] = []
            for task in ready:
                if cancel_event is not None and cancel_event.is_set():
                    task.transition(TaskStatus.CANCELLED)
                    self.board.record("task_cancelled", task_id=task.task_id)
                    continue
                if batch and (not self._is_read_only(task) or any(not self._is_read_only(item) for item in batch)):
                    continue
                if any(self._files_conflict(task, item) for item in batch):
                    continue
                batch.append(task)
                if len(batch) >= self.max_concurrency:
                    break
            if not batch:
                batch = [ready[0]]

            async def run_one(task: AgentTask) -> None:
                task.transition(TaskStatus.RUNNING)
                self.board.record("task_started", task_id=task.task_id, role=task.role)
                try:
                    summary, artifacts = await worker(task, self.board.view_for(task.role, task.task_id))
                    task.result_summary, task.artifact_refs = summary, artifacts
                    task.transition(TaskStatus.COMPLETED)
                    self.bus.send(AgentMessage("supervisor", task.role, MessageType.TASK_RESULT, task.task_id, {"summary": summary}, artifacts))
                    self.board.record("task_completed", task_id=task.task_id, role=task.role)
                except asyncio.CancelledError:
                    task.transition(TaskStatus.CANCELLED)
                    self.board.record("task_cancelled", task_id=task.task_id)
                except Exception as exc:
                    task.error = str(exc)
                    if task.retry_count < task.max_retries:
                        task.retry_count += 1
                        task.transition(TaskStatus.FAILED)
                        task.transition(TaskStatus.READY)
                        self.board.record("task_retry", task_id=task.task_id, retry=task.retry_count)
                    else:
                        task.transition(TaskStatus.FAILED)
                        self.board.record("task_failed", task_id=task.task_id, error=task.error)
            await asyncio.gather(*(run_one(task) for task in batch))

    @staticmethod
    def _files_conflict(left: AgentTask, right: AgentTask) -> bool:
        if not left.files or not right.files:
            return not (StructuredTaskScheduler._is_read_only(left) and StructuredTaskScheduler._is_read_only(right))
        return bool(set(left.files) & set(right.files))


def review_passed(report: str) -> bool:
    """Accept structured verdicts and the legacy explicit PASS convention."""
    return parse_review_decision(report).passed


AgentWorker = Callable[[AgentAssignment, SharedTaskBoard], Awaitable[str]]
Reviewer = Callable[[SharedTaskBoard], Awaitable[str]]
Tester = Callable[[SharedTaskBoard], Awaitable[str]]


class CollaborativeRunner:
    """Run role-separated workers against a shared board, then review output."""

    def __init__(self, max_concurrency: int = 2) -> None:
        self.max_concurrency = max(1, max_concurrency)

    async def run(
        self,
        objective: str,
        assignments: list[AgentAssignment],
        worker: AgentWorker,
        reviewer: Reviewer,
    ) -> SharedTaskBoard:
        board = SharedTaskBoard(objective, [BoardEntry(item.role, item.objective) for item in assignments])
        for assignment, entry in zip(assignments, board.entries):
            task = AgentTask(
                goal=assignment.objective,
                role=assignment.role,
                allowed_tools=sorted(ROLE_TOOL_POLICY.get(assignment.role, set())),
            )
            entry.task_id = task.task_id
            board.add_task(task)
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def run_one(assignment: AgentAssignment, entry: BoardEntry) -> None:
            entry.status = "running"
            task = board.tasks[entry.task_id]
            task.transition(TaskStatus.READY)
            task.transition(TaskStatus.RUNNING)
            board.record("agent_started", task_id=task.task_id, agent_id=entry.role)
            try:
                async with semaphore:
                    entry.result = await worker(assignment, board)
                entry.status = "completed"
                task.result_summary = entry.result
                task.transition(TaskStatus.COMPLETED)
                board.record("agent_completed", task_id=task.task_id, agent_id=entry.role)
            except Exception as exc:
                entry.status = "failed"
                entry.result = str(exc)
                task.error = str(exc)
                task.transition(TaskStatus.FAILED)
                board.record("agent_failed", task_id=task.task_id, agent_id=entry.role, error=str(exc))

        await asyncio.gather(*(run_one(item, entry) for item, entry in zip(assignments, board.entries)))
        review_task = AgentTask(
            goal="Review completed implementation artifacts.", role="reviewer",
            allowed_tools=sorted(ROLE_TOOL_POLICY["reviewer"]),
        )
        board.add_task(review_task)
        review_task.transition(TaskStatus.READY)
        review_task.transition(TaskStatus.RUNNING)
        board.review = await reviewer(board)
        review_task.result_summary = board.review
        review_task.transition(TaskStatus.COMPLETED)
        board.record("review_completed", task_id=review_task.task_id, verdict=parse_review_decision(board.review).verdict)
        return board

    async def run_review_loop(
        self,
        objective: str,
        assignments: list[AgentAssignment],
        worker: AgentWorker,
        reviewer: Reviewer,
        tester: Tester,
        max_review_cycles: int = 2,
    ) -> SharedTaskBoard:
        """Schedule Coding -> Review -> (Fix -> Review)* -> Test.

        The reviewer only decides whether the coding result is acceptable.
        A failed review is scheduler input: it creates a new coding task, and
        dependent testing remains locked until a review explicitly passes.
        """
        board = await self.run(objective, assignments, worker, reviewer)
        for _ in range(max(0, max_review_cycles)):
            board.review_history.append(board.review)
            if review_passed(board.review):
                test_task = AgentTask(
                    goal="Run relevant tests after review approval.", role="tester",
                    allowed_tools=sorted(ROLE_TOOL_POLICY["tester"]),
                )
                board.add_task(test_task)
                test_task.transition(TaskStatus.READY)
                test_task.transition(TaskStatus.RUNNING)
                board.verification = await tester(board)
                test_task.result_summary = board.verification
                test_task.transition(TaskStatus.COMPLETED)
                board.record("test_completed", task_id=test_task.task_id, verdict=parse_review_decision(board.verification).verdict)
                board.outcome = "accepted" if review_passed(board.verification) else "test_failed"
                return board

            repair = AgentAssignment(
                "implementer",
                "Fix every blocking issue from this review:\n" + board.review,
            )
            repair_task = AgentTask(
                goal=repair.objective, role="implementer",
                allowed_tools=sorted(ROLE_TOOL_POLICY["implementer"]),
            )
            board.add_task(repair_task)
            repair_task.transition(TaskStatus.READY)
            repair_task.transition(TaskStatus.RUNNING)
            entry = BoardEntry("implementer", "Fix reviewer findings", repair_task.task_id, status="running")
            board.entries.append(entry)
            try:
                entry.result = await worker(repair, board)
                entry.status = "completed"
                repair_task.result_summary = entry.result
                repair_task.transition(TaskStatus.COMPLETED)
                board.record("repair_completed", task_id=repair_task.task_id, agent_id="implementer")
            except Exception as exc:
                entry.result = str(exc)
                entry.status = "failed"
                repair_task.error = str(exc)
                repair_task.transition(TaskStatus.FAILED)
                board.outcome = "repair_failed"
                return board
            board.review = await reviewer(board)

        board.review_history.append(board.review)
        board.outcome = "review_failed"
        return board
