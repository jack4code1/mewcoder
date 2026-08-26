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

    def summary(self) -> str:
        return "\n".join(
            f"[{entry.role}] {entry.objective}: {entry.result}" for entry in self.entries
        )


def review_passed(report: str) -> bool:
    """Accept only an explicit final PASS verdict from a reviewing agent."""
    return report.upper().rstrip().endswith("VERDICT: PASS")


AgentWorker = Callable[[AgentAssignment, SharedTaskBoard], Awaitable[str]]
Reviewer = Callable[[SharedTaskBoard], Awaitable[str]]


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
