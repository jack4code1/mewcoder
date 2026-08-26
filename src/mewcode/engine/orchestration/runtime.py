"""Single-process primitives for bounded, observable multi-agent execution.

These types deliberately do not create model processes.  A runtime owns one
private conversation and is driven by an injected executor (normally the
existing ReAct loop).  This makes the coordination protocol usable by the TUI
today and replaceable by a remote worker later.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from time import monotonic
from typing import Any, Awaitable, Callable
from uuid import uuid4

from .tool_policy import ROLE_TOOL_POLICY, allowed_tools_for_role


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageType(str, Enum):
    TASK_ASSIGN = "TASK_ASSIGN"
    TASK_RESULT = "TASK_RESULT"
    HELP_REQUEST = "HELP_REQUEST"
    REVIEW_REQUEST = "REVIEW_REQUEST"
    REVIEW_FEEDBACK = "REVIEW_FEEDBACK"
    TEST_RESULT = "TEST_RESULT"
    TASK_FAILED = "TASK_FAILED"
    TASK_CANCEL = "TASK_CANCEL"
    REPLAN_REQUEST = "REPLAN_REQUEST"
    ARTIFACT_UPDATED = "ARTIFACT_UPDATED"


_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.READY, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.READY: {TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.BLOCKED: {TaskStatus.READY, TaskStatus.CANCELLED},
    TaskStatus.FAILED: {TaskStatus.READY, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}


@dataclass
class AgentTask:
    goal: str
    role: str
    task_id: str = field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    parent_task_id: str | None = None
    depends_on: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    input_artifacts: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 2
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    error: str = ""
    result_summary: str = ""
    artifact_refs: list[str] = field(default_factory=list)

    def transition(self, target: TaskStatus) -> None:
        if target not in _TRANSITIONS[self.status]:
            raise ValueError(f"invalid task transition: {self.status.value} -> {target.value}")
        self.status = target
        self.updated_at = utc_now()


@dataclass(frozen=True)
class AgentMessage:
    sender: str
    receiver: str
    type: MessageType
    task_id: str
    content: dict[str, Any] = field(default_factory=dict)
    artifact_refs: list[str] = field(default_factory=list)
    message_id: str = field(default_factory=lambda: f"msg_{uuid4().hex[:12]}")
    created_at: str = field(default_factory=utc_now)


@dataclass
class TraceEvent:
    kind: str
    run_id: str
    task_id: str | None = None
    agent_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass
class TaskResult:
    status: TaskStatus
    summary: str = ""
    artifact_refs: list[str] = field(default_factory=list)
    error: str = ""
    token_count: int = 0


@dataclass(frozen=True)
class ReviewDecision:
    verdict: str
    feedback: str = ""
    artifact_refs: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.verdict == "PASS"


def parse_review_decision(value: str | dict[str, Any]) -> ReviewDecision:
    """Prefer a structured verdict while accepting legacy ``VERDICT:`` text."""
    if isinstance(value, dict):
        verdict = str(value.get("verdict", "")).upper()
        if verdict in {"PASS", "FIX"}:
            return ReviewDecision(verdict, str(value.get("feedback", "")), tuple(value.get("artifact_refs", [])))
    text = str(value).strip()
    verdict = "PASS" if text.upper().rstrip().endswith("VERDICT: PASS") else "FIX"
    return ReviewDecision(verdict, text)


class InMemoryMessageBus:
    """Validated, idempotent in-process inboxes; role receivers fan out."""

    def __init__(self) -> None:
        self._agents: dict[str, str] = {}
        self._inboxes: dict[str, deque[AgentMessage]] = defaultdict(deque)
        self._seen: set[str] = set()
        self.audit: list[AgentMessage] = []

    def register(self, agent_id: str, role: str) -> None:
        if not agent_id or agent_id in self._agents:
            raise ValueError("agent_id must be unique and non-empty")
        self._agents[agent_id] = role

    def send(self, message: AgentMessage) -> int:
        if message.message_id in self._seen:
            return 0
        if message.sender != "supervisor" and message.sender not in self._agents:
            raise ValueError("unknown message sender")
        recipients = ([message.receiver] if message.receiver in self._agents else
                      [agent_id for agent_id, role in self._agents.items() if role == message.receiver])
        if not recipients:
            raise ValueError("unknown message receiver")
        self._seen.add(message.message_id)
        self.audit.append(message)
        for receiver in recipients:
            self._inboxes[receiver].append(message)
        return len(recipients)

    def consume(self, agent_id: str, *, task_id: str | None = None) -> list[AgentMessage]:
        if agent_id not in self._agents:
            raise ValueError("unknown agent")
        inbox = self._inboxes[agent_id]
        kept: deque[AgentMessage] = deque()
        consumed: list[AgentMessage] = []
        while inbox:
            message = inbox.popleft()
            if task_id is None or message.task_id == task_id:
                consumed.append(message)
            else:
                kept.append(message)
        self._inboxes[agent_id] = kept
        return consumed


class TaskGraph:
    """Validated task DAG with explicit state transitions and bounded expansion."""

    def __init__(self, *, registered_tools: set[str], max_dynamic_tasks: int = 12) -> None:
        self.registered_tools = set(registered_tools)
        self.max_dynamic_tasks = max(0, max_dynamic_tasks)
        self.tasks: dict[str, AgentTask] = {}

    def add(self, task: AgentTask, *, dynamic: bool = False) -> None:
        if task.task_id in self.tasks:
            raise ValueError(f"duplicate task id: {task.task_id}")
        if dynamic and len(self.tasks) >= self.max_dynamic_tasks:
            raise ValueError("dynamic task limit reached")
        if task.role not in ROLE_TOOL_POLICY:
            raise ValueError(f"unknown task role: {task.role}")
        if not set(task.allowed_tools) <= self.registered_tools:
            raise ValueError("task requests an unregistered tool")
        role_tools = ROLE_TOOL_POLICY[task.role]
        if not set(task.allowed_tools) <= role_tools:
            raise ValueError("task requests tools outside its role policy")
        if task.parent_task_id is not None and task.parent_task_id not in self.tasks:
            raise ValueError("parent task does not exist")
        if not set(task.depends_on) <= self.tasks.keys():
            raise ValueError("task has unknown dependency")
        if task.task_id in task.depends_on:
            raise ValueError("task cannot depend on itself")
        self.tasks[task.task_id] = task
        try:
            self._validate_acyclic()
        except Exception:
            del self.tasks[task.task_id]
            raise

    def _validate_acyclic(self) -> None:
        visiting, visited = set(), set()
        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ValueError("task dependency graph contains a cycle")
            if task_id not in visited:
                visiting.add(task_id)
                for dependency in self.tasks[task_id].depends_on:
                    visit(dependency)
                visiting.remove(task_id)
                visited.add(task_id)
        for task_id in self.tasks:
            visit(task_id)

    def refresh_ready(self) -> list[AgentTask]:
        ready: list[AgentTask] = []
        for task in self.tasks.values():
            if task.status not in {TaskStatus.PENDING, TaskStatus.BLOCKED, TaskStatus.READY}:
                continue
            dependencies = [self.tasks[item] for item in task.depends_on]
            if any(item.status in {TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.BLOCKED} for item in dependencies):
                if task.status is TaskStatus.PENDING:
                    task.transition(TaskStatus.BLOCKED)
                continue
            if all(item.status is TaskStatus.COMPLETED for item in dependencies):
                if task.status is not TaskStatus.READY:
                    task.transition(TaskStatus.READY)
                ready.append(task)
        return sorted(ready, key=lambda item: (-item.priority, item.created_at))

    def permitted_tools(self, task: AgentTask) -> set[str]:
        return allowed_tools_for_role(task.role, self.registered_tools, set(task.allowed_tools))


class DynamicTaskController:
    """Bounded supervisor actions triggered by protocol messages.

    It accepts only structured HELP/REPLAN requests and never lets a sender
    expand role permissions.  Actual planning remains injected by the caller.
    """

    def __init__(self, graph: TaskGraph, *, max_replans: int = 2) -> None:
        self.graph = graph
        self.max_replans = max(0, max_replans)
        self.replans = 0

    def create_help_task(self, request: AgentMessage) -> AgentTask:
        if request.type is not MessageType.HELP_REQUEST:
            raise ValueError("expected HELP_REQUEST")
        source = self.graph.tasks.get(request.task_id)
        if source is None:
            raise ValueError("help request references an unknown task")
        content = request.content
        role = str(content.get("role", "researcher"))
        task = AgentTask(
            goal=str(content.get("goal", "Provide information needed by the parent task.")),
            role=role,
            parent_task_id=source.task_id,
            files=list(content.get("files", [])),
            allowed_tools=list(content.get("allowed_tools", [])),
            priority=max(source.priority + 1, 1),
        )
        self.graph.add(task, dynamic=True)
        source.depends_on.append(task.task_id)
        return task

    def request_replan(self, request: AgentMessage) -> bool:
        if request.type is not MessageType.REPLAN_REQUEST:
            raise ValueError("expected REPLAN_REQUEST")
        if request.task_id not in self.graph.tasks or self.replans >= self.max_replans:
            return False
        self.replans += 1
        return True


AgentExecutor = Callable[["AgentRuntime", AgentTask, dict[str, Any]], Awaitable[TaskResult]]


@dataclass
class AgentRuntime:
    agent_id: str
    role: str
    capabilities: set[str]
    conversation: Any
    allowed_tools: set[str]
    token_budget: int = 32_000
    step_budget: int = 20
    timeout_seconds: float = 300
    private_state: dict[str, Any] = field(default_factory=dict)
    current_task: AgentTask | None = None
    status: AgentStatus = AgentStatus.IDLE
    message_inbox: list[AgentMessage] = field(default_factory=list)

    async def run(
        self, task: AgentTask, board_view: dict[str, Any], executor: AgentExecutor,
        cancel_event: asyncio.Event | None = None,
    ) -> TaskResult:
        if task.role != self.role:
            raise ValueError("task role does not match agent runtime")
        if not set(task.allowed_tools) <= self.allowed_tools:
            raise PermissionError("task tool request exceeds runtime permissions")
        if cancel_event is not None and cancel_event.is_set():
            self.status = AgentStatus.CANCELLED
            return TaskResult(TaskStatus.CANCELLED, error="cancelled")
        self.current_task, self.status = task, AgentStatus.RUNNING
        started = monotonic()
        try:
            async with asyncio.timeout(self.timeout_seconds):
                result = await executor(self, task, board_view)
            if cancel_event is not None and cancel_event.is_set():
                result = TaskResult(TaskStatus.CANCELLED, error="cancelled")
            if result.token_count > self.token_budget:
                result = TaskResult(TaskStatus.FAILED, error="token budget exceeded", token_count=result.token_count)
            self.private_state["last_duration_ms"] = int((monotonic() - started) * 1000)
            self.private_state["last_result"] = result.summary[:2000]
            self.status = AgentStatus(result.status.value)
            return result
        except TimeoutError:
            self.status = AgentStatus.FAILED
            return TaskResult(TaskStatus.FAILED, error="agent timeout")
        except asyncio.CancelledError:
            self.status = AgentStatus.CANCELLED
            return TaskResult(TaskStatus.CANCELLED, error="cancelled")
        except Exception as exc:
            self.status = AgentStatus.FAILED
            return TaskResult(TaskStatus.FAILED, error=str(exc))
