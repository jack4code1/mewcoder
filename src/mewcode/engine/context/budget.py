"""Token budget defaults and deterministic allocation helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextBudget:
    total_tokens: int = 16_000
    reserved_response_tokens: int = 2_000

    @property
    def input_tokens(self) -> int:
        return max(0, self.total_tokens - self.reserved_response_tokens)

    def cap(self, requested: int | None = None) -> int:
        return min(self.input_tokens, requested) if requested is not None else self.input_tokens
