"""Append-only, redacted audit storage for controlled operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, workspace: Path) -> None:
        self.path = workspace / ".mewcode" / "audit.jsonl"

    def append(self, entry: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        safe = {key: value for key, value in entry.items() if key not in {"input", "api_key", "token"}}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe, ensure_ascii=False) + "\n")
