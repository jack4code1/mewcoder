import pytest

from mewcode.engine.context import MemoryRecord, ProjectMemoryStore
from mewcode.engine.orchestration import (
    AgentAssignment,
    CollaborativeRunner,
    PlanExecutor,
    PlanStep,
    TaskFailureAction,
    TaskScheduler,
    parse_task_plan,
    review_passed,
)


@pytest.mark.asyncio
async def test_plan_executor_replans_after_a_failed_step():
    calls = []

    async def planner(objective, previous):
        calls.append([step.status for step in previous])
        return [PlanStep("retry")] if previous else [PlanStep("fails")]

    async def executor(step, steps):
        if step.objective == "fails":
            raise RuntimeError("blocked")
        return "done"

    plan = await PlanExecutor(max_replans=1).run("objective", planner, executor)

    assert plan.replans == 1
    assert [step.status for step in plan.steps] == ["completed"]
    assert calls == [[], ["failed"]]


@pytest.mark.asyncio
async def test_collaborative_runner_shares_board_then_reviews():
    seen = []

    async def worker(assignment, board):
        seen.append((assignment.role, board.objective))
        return f"{assignment.role} result"

    async def reviewer(board):
        return "reviewed: " + board.summary()

    board = await CollaborativeRunner().run(
        "ship feature",
        [AgentAssignment("researcher", "inspect"), AgentAssignment("implementer", "change")],
        worker,
        reviewer,
    )

    assert {item[0] for item in seen} == {"researcher", "implementer"}
    assert all(entry.status == "completed" for entry in board.entries)
    assert "implementer result" in board.review


@pytest.mark.asyncio
async def test_review_loop_repairs_then_rechecks_before_running_tests():
    events = []
    reviews = iter(["Missing validation\nVERDICT: FIX", "Looks correct\nVERDICT: PASS"])

    async def worker(assignment, _board):
        events.append(f"code:{assignment.role}")
        return assignment.objective

    async def reviewer(_board):
        events.append("review")
        return next(reviews)

    async def tester(_board):
        events.append("test")
        return "Tests pass\nVERDICT: PASS"

    board = await CollaborativeRunner(max_concurrency=1).run_review_loop(
        "ship feature",
        [AgentAssignment("implementer", "initial change")],
        worker,
        reviewer,
        tester,
    )

    assert events == ["code:implementer", "review", "code:implementer", "review", "test"]
    assert len(board.review_history) == 2
    assert board.outcome == "accepted"


def test_memory_persists_vector_and_returns_relevant_records(tmp_path):
    store = ProjectMemoryStore(tmp_path)
    record = store.save(MemoryRecord("Python tests use pytest", kind="auto"))

    loaded = store.list()[0]
    assert loaded.vector and len(loaded.vector) == 128
    assert store.relevant("run Python tests")[0].id == record.id


def test_review_requires_an_explicit_final_pass_verdict():
    assert review_passed("Tests passed\nVERDICT: PASS")
    assert not review_passed("Tests passed but inspect later")
    assert not review_passed("VERDICT: FIX")


@pytest.mark.asyncio
async def test_task_scheduler_unlocks_dependents_after_react_task_completion():
    plan = parse_task_plan(
        '{"tasks":['
        '{"id":"inspect","description":"inspect","role":"researcher","depends_on":[],"files":["a.py"],"allowed_tools":["ReadFile"]},'
        '{"id":"change","description":"change","role":"implementer","depends_on":["inspect"],"files":["a.py"],"allowed_tools":["EditFile"]}'
        ']}',
        "objective",
        {"ReadFile", "EditFile"},
    )
    seen = []

    async def worker(task, _plan):
        seen.append(task.id)
        return task.id

    await TaskScheduler().run(plan, worker)

    assert seen == ["inspect", "change"]
    assert [task.status for task in plan.tasks] == ["completed", "completed"]


def test_task_plan_rejects_cycles_and_unknown_tools():
    with pytest.raises(ValueError, match="cycle"):
        parse_task_plan(
            '{"tasks":[{"id":"a","description":"a","role":"x","depends_on":["b"],"files":[],"allowed_tools":[]},{"id":"b","description":"b","role":"x","depends_on":["a"],"files":[],"allowed_tools":[]}]}',
            "objective", set(),
        )
    with pytest.raises(ValueError, match="unavailable"):
        parse_task_plan(
            '{"tasks":[{"id":"a","description":"a","role":"x","depends_on":[],"files":[],"allowed_tools":["Bash"]}]}',
            "objective", {"ReadFile"},
        )


def test_task_scheduler_serializes_overlapping_or_unknown_file_resources():
    scheduler = TaskScheduler(max_concurrency=3)
    assert [task.id for task in scheduler._non_conflicting_batch([
        _task("a", ["src/app.py"]),
        _task("b", ["src/app.py"]),
        _task("c", ["tests/test_app.py"]),
    ])] == ["a", "c"]
    assert [task.id for task in scheduler._non_conflicting_batch([
        _task("a", ["src/**/*.py"]),
        _task("b", ["src/app.py"]),
    ])] == ["a"]
    assert [task.id for task in scheduler._non_conflicting_batch([
        _task("a", []),
        _task("b", ["src/app.py"]),
    ])] == ["a"]


@pytest.mark.asyncio
async def test_scheduler_blocks_dependents_and_records_failure():
    plan = parse_task_plan(
        '{"tasks":[{"id":"prepare","description":"prepare","role":"implementer","depends_on":[],"files":["a.py"],"allowed_tools":[]},{"id":"verify","description":"verify","role":"reviewer","depends_on":["prepare"],"files":["b.py"],"allowed_tools":[]}]}',
        "objective", set(),
    )
    seen = []

    async def worker(task, _plan):
        seen.append(task.id)
        raise RuntimeError("build failed")

    await TaskScheduler().run(plan, worker)

    assert seen == ["prepare"]
    assert plan.failed_task_id == "prepare"
    assert [(task.status, task.error) for task in plan.tasks] == [("failed", "build failed"), ("blocked", "")]


@pytest.mark.asyncio
async def test_scheduler_retries_only_when_policy_allows_it():
    plan = parse_task_plan(
        '{"tasks":[{"id":"change","description":"change","role":"implementer","depends_on":[],"files":["a.py"],"allowed_tools":[]}]}',
        "objective", set(),
    )

    async def worker(task, _plan):
        if task.attempts == 1:
            raise RuntimeError("transient")
        return "done"

    await TaskScheduler(
        failure_policy=lambda _task, _plan: TaskFailureAction.RETRY,
        max_task_retries=1,
    ).run(plan, worker)

    assert plan.outcome == "completed"
    assert plan.tasks[0].attempts == 2
    assert plan.tasks[0].status == "completed"


def _task(task_id, files):
    from mewcode.engine.orchestration.planning import PlanTask

    return PlanTask(task_id, task_id, "implementer", files=files)
