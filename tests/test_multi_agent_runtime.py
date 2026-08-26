import asyncio
import subprocess

import pytest

from mewcode.engine.conversation import ConversationManager
from mewcode.engine.orchestration import (
    AgentMessage,
    AgentRuntime,
    AgentTask,
    DynamicTaskController,
    InMemoryMessageBus,
    MessageType,
    SharedTaskBoard,
    StructuredTaskScheduler,
    TaskGraph,
    TaskResult,
    TaskStatus,
    WorktreeManager,
    WorktreeTaskScheduler,
    parse_review_decision,
)


TOOLS = {"Glob", "Grep", "ReadFile", "EditFile", "WriteFile", "Bash", "Diff"}


def task(goal, role, **kwargs):
    return AgentTask(goal=goal, role=role, **kwargs)


def test_task_graph_validates_roles_dependencies_and_tool_escalation():
    graph = TaskGraph(registered_tools=TOOLS)
    graph.add(task("inspect", "researcher", task_id="inspect", allowed_tools=["ReadFile"]))
    graph.add(task("edit", "implementer", task_id="edit", depends_on=["inspect"], allowed_tools=["EditFile"]))

    assert graph.permitted_tools(graph.tasks["edit"]) == {"EditFile"}
    with pytest.raises(ValueError, match="outside its role"):
        graph.add(task("bad", "reviewer", task_id="bad", allowed_tools=["EditFile"]))
    with pytest.raises(ValueError, match="unknown dependency"):
        graph.add(task("missing", "tester", task_id="missing", depends_on=["nope"], allowed_tools=[]))


def test_task_graph_state_transitions_and_failed_dependencies_block_downstream():
    graph = TaskGraph(registered_tools=TOOLS)
    first = task("inspect", "researcher", task_id="a", allowed_tools=[])
    second = task("edit", "implementer", task_id="b", depends_on=["a"], allowed_tools=[])
    graph.add(first)
    graph.add(second)
    assert [item.task_id for item in graph.refresh_ready()] == ["a"]
    first.transition(TaskStatus.RUNNING)
    first.transition(TaskStatus.FAILED)
    graph.refresh_ready()
    assert second.status is TaskStatus.BLOCKED
    with pytest.raises(ValueError, match="invalid task transition"):
        first.transition(TaskStatus.COMPLETED)


def test_message_bus_routes_deduplicates_and_rejects_invalid_recipients():
    bus = InMemoryMessageBus()
    bus.register("research-1", "researcher")
    bus.register("review-1", "reviewer")
    message = AgentMessage("supervisor", "researcher", MessageType.TASK_ASSIGN, "task_1", {"goal": "inspect"})

    assert bus.send(message) == 1
    assert bus.send(message) == 0
    assert bus.consume("research-1", task_id="task_1") == [message]
    with pytest.raises(ValueError, match="receiver"):
        bus.send(AgentMessage("supervisor", "missing", MessageType.TASK_ASSIGN, "task_1"))


@pytest.mark.asyncio
async def test_runtime_keeps_private_context_and_enforces_tool_and_timeout_budgets():
    first = AgentRuntime("a", "researcher", {"ReadFile"}, ConversationManager(), {"ReadFile"}, token_budget=5)
    second = AgentRuntime("b", "researcher", {"ReadFile"}, ConversationManager(), {"ReadFile"})
    work = task("inspect", "researcher", allowed_tools=["ReadFile"])

    async def over_budget(_agent, _task, _view):
        return TaskResult(TaskStatus.COMPLETED, "done", token_count=6)

    result = await first.run(work, {"secret": "not copied"}, over_budget)
    assert result.status is TaskStatus.FAILED
    assert second.private_state == {}
    with pytest.raises(PermissionError):
        await first.run(task("bad", "researcher", allowed_tools=["Grep"]), {}, over_budget)

    slow = AgentRuntime("slow", "researcher", set(), ConversationManager(), set(), timeout_seconds=0.01)
    async def wait(_agent, _task, _view):
        await asyncio.sleep(0.1)
        return TaskResult(TaskStatus.COMPLETED)
    assert (await slow.run(task("wait", "researcher"), {}, wait)).error == "agent timeout"


@pytest.mark.asyncio
async def test_structured_scheduler_allows_read_concurrency_but_serializes_writes_and_retries():
    graph = TaskGraph(registered_tools=TOOLS)
    read_a = task("a", "researcher", task_id="read-a", files=["a.py"], allowed_tools=["ReadFile"])
    read_b = task("b", "researcher", task_id="read-b", files=["b.py"], allowed_tools=["ReadFile"])
    write_a = task("write a", "implementer", task_id="write-a", files=["a.py"], allowed_tools=["EditFile"], max_retries=1)
    write_b = task("write b", "implementer", task_id="write-b", files=["b.py"], allowed_tools=["EditFile"])
    for item in (read_a, read_b, write_a, write_b):
        graph.add(item)
    board = SharedTaskBoard("objective")
    for item in graph.tasks.values():
        board.add_task(item)
    bus = InMemoryMessageBus()
    bus.register("research", "researcher")
    bus.register("implement", "implementer")
    scheduler = StructuredTaskScheduler(graph, board, bus, max_concurrency=2)
    active = peak = 0
    calls = []

    async def worker(item, _view):
        nonlocal active, peak
        calls.append(item.task_id)
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        if item.task_id == "write-a" and item.retry_count == 0:
            raise RuntimeError("transient")
        return item.task_id, [f"artifact:{item.task_id}"]

    await scheduler.run(worker)

    assert peak == 2
    assert calls.count("write-a") == 2
    assert all(item.status is TaskStatus.COMPLETED for item in graph.tasks.values())
    assert bus.audit


def test_board_view_only_exposes_current_task_dependencies_and_addressed_messages():
    board = SharedTaskBoard("objective")
    parent = task("inspect", "researcher", task_id="parent", allowed_tools=[])
    child = task("implement", "implementer", task_id="child", depends_on=["parent"], allowed_tools=[])
    parent.result_summary = "relevant files"
    board.add_task(parent)
    board.add_task(child)
    board.add_message(AgentMessage("research", "implementer", MessageType.TASK_RESULT, "child", {"summary": "use a.py"}))
    board.add_message(AgentMessage("other", "reviewer", MessageType.TASK_RESULT, "child", {"secret": "hidden"}))

    view = board.view_for("implementer-1", "child")
    assert view["dependencies"][0]["summary"] == "relevant files"
    assert view["messages"] == [{"type": "TASK_RESULT", "content": {"summary": "use a.py"}, "artifact_refs": []}]


def test_dynamic_help_tasks_and_replan_requests_are_bounded():
    graph = TaskGraph(registered_tools=TOOLS, max_dynamic_tasks=2)
    parent = task("implement", "implementer", task_id="parent", allowed_tools=["EditFile"])
    graph.add(parent)
    controller = DynamicTaskController(graph, max_replans=1)
    request = AgentMessage(
        "implementer-1", "supervisor", MessageType.HELP_REQUEST, "parent",
        {"goal": "find public API", "role": "researcher", "allowed_tools": ["ReadFile"]},
    )
    child = controller.create_help_task(request)
    assert child.parent_task_id == "parent"
    assert child.task_id in parent.depends_on
    replan = AgentMessage("implementer-1", "supervisor", MessageType.REPLAN_REQUEST, "parent")
    assert controller.request_replan(replan)
    assert not controller.request_replan(replan)


def test_structured_and_legacy_review_verdicts_are_supported():
    assert parse_review_decision({"verdict": "PASS", "feedback": "ok"}).passed
    assert parse_review_decision("legacy\nVERDICT: PASS").passed
    assert not parse_review_decision("needs change\nVERDICT: FIX").passed


def _git_repo(path):
    for args in (("init",), ("config", "user.email", "test@example.com"), ("config", "user.name", "Test")):
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)
    (path / "base.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, check=True, capture_output=True)


@pytest.mark.asyncio
async def test_worktree_scheduler_isolates_write_diff_until_explicit_apply(tmp_path):
    _git_repo(tmp_path)
    graph = TaskGraph(registered_tools=TOOLS)
    change = task("change", "implementer", task_id="change", files=["base.txt"], allowed_tools=["EditFile"])
    graph.add(change)
    board = SharedTaskBoard("objective")
    board.add_task(change)
    bus = InMemoryMessageBus()
    bus.register("implementer-1", "implementer")
    scheduler = WorktreeTaskScheduler(graph, board, bus, WorktreeManager(tmp_path))

    async def worker(_task, _view, lease):
        assert lease is not None
        (lease.path / "base.txt").write_text("isolated\n", encoding="utf-8")
        return "changed", []

    await scheduler.run(worker)

    assert (tmp_path / "base.txt").read_text(encoding="utf-8") == "base\n"
    assert "diff:change" in board.artifacts
    assert "+isolated" in board.artifacts["diff:change"]["content"]
    scheduler.apply("change")
    assert (tmp_path / "base.txt").read_text(encoding="utf-8") == "isolated\n"
