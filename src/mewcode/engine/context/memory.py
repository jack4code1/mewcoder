"""Project-local persistent facts, preferences, and decisions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4


@dataclass
class MemoryRecord:
    content: str
    kind: str = "fact"
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid4().hex


class ProjectMemoryStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.path = self.workspace / ".mewcode" / "memory.json"

    def list(self) -> list[MemoryRecord]:
        if not self.path.exists():
            return []
        return [MemoryRecord(**item) for item in json.loads(self.path.read_text(encoding="utf-8"))]

    def save(self, record: MemoryRecord) -> MemoryRecord:
        records = self.list()
        records = [item for item in records if item.id != record.id] + [record]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(item) for item in records], ensure_ascii=False), encoding="utf-8")
        return record

    def delete(self, record_id: str) -> bool:
        records = self.list()
        kept = [item for item in records if item.id != record_id]
        if len(kept) == len(records):
            return False
        self.path.write_text(json.dumps([asdict(item) for item in kept], ensure_ascii=False), encoding="utf-8")
        return True
