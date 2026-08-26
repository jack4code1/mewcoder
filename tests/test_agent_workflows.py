import pytest

from mewcode.engine.context import MemoryRecord, ProjectMemoryStore
from mewcode.engine.orchestration import (
    AgentAssignment,
    CollaborativeRunner,
    PlanExecutor,
    PlanStep,
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
