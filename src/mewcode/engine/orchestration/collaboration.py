"""Shared-board collaboration for independently prompted agent roles."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable


@dataclass(frozen=True)
class AgentAssignment:
    role: str
    objective: str


@dataclass
class BoardEntry:
    role: str
    objective: str
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

    def summary(self) -> str:
        return "\n".join(
            f"[{entry.role}] {entry.objective}: {entry.result}" for entry in self.entries
        )


def review_passed(report: str) -> bool:
    """Accept only an explicit final PASS verdict from a reviewing agent."""
    return report.upper().rstrip().endswith("VERDICT: PASS")


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
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def run_one(assignment: AgentAssignment, entry: BoardEntry) -> None:
            entry.status = "running"
            try:
                async with semaphore:
                    entry.result = await worker(assignment, board)
                entry.status = "completed"
            except Exception as exc:
                entry.status = "failed"
                entry.result = str(exc)

        await asyncio.gather(*(run_one(item, entry) for item, entry in zip(assignments, board.entries)))
        board.review = await reviewer(board)
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
                board.verification = await tester(board)
                board.outcome = "accepted" if review_passed(board.verification) else "test_failed"
                return board

            repair = AgentAssignment(
                "implementer",
                "Fix every blocking issue from this review:\n" + board.review,
            )
            entry = BoardEntry("implementer", "Fix reviewer findings", status="running")
            board.entries.append(entry)
            try:
                entry.result = await worker(repair, board)
                entry.status = "completed"
            except Exception as exc:
                entry.result = str(exc)
                entry.status = "failed"
                board.outcome = "repair_failed"
                return board
            board.review = await reviewer(board)

        board.review_history.append(board.review)
        board.outcome = "review_failed"
        return board
