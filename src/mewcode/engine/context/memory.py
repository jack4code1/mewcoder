"""Project-local persistent facts, preferences, and decisions."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
import os
from typing import Any

import httpx
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4


@dataclass
class MemoryRecord:
    content: str
    kind: str = "fact"
    id: str = ""
    vector: list[float] | None = None
    source: str = "manual"
    confidence: float = 1.0
    status: str = "active"
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid4().hex
        if self.vector is None:
            self.vector = embed(self.content)
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


_VECTOR_SIZE = 128


def embed(text: str) -> list[float]:
    """Create a deterministic local feature vector without another API call."""
    vector = [0.0] * _VECTOR_SIZE
    for token in re.findall(r"[\w]+", text.casefold(), flags=re.UNICODE):
        index = int.from_bytes(token.encode("utf-8"), "little", signed=False) % _VECTOR_SIZE
        vector[index] += 1.0
    length = math.sqrt(sum(value * value for value in vector))
    return [value / length for value in vector] if length else vector


def similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


class ProjectMemoryStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.path = self.workspace / ".mewcode" / "memory.json"

    def list(self, status: str | None = None) -> list[MemoryRecord]:
        if not self.path.exists():
            return []
        records = [MemoryRecord(**item) for item in json.loads(self.path.read_text(encoding="utf-8"))]
        return [record for record in records if status is None or record.status == status]

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

    def approve(self, record_id: str) -> MemoryRecord | None:
        records = self.list()
        record = next((item for item in records if item.id == record_id and item.status == "pending"), None)
        if record is None:
            return None
        record.status = "active"
        self._write(records)
        return record

    def reject(self, record_id: str) -> bool:
        records = self.list()
        kept = [item for item in records if item.id != record_id or item.status != "pending"]
        if len(kept) == len(records):
            return False
        self._write(kept)
        return True

    def _write(self, records: list[MemoryRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(item) for item in records], ensure_ascii=False), encoding="utf-8")

    def search(self, query: str, limit: int = 10) -> list[MemoryRecord]:
        terms = [term.casefold() for term in query.split() if term]
        if not terms:
            return []
        query_vector = embed(query)
        ranked = []
        for record in self.list("active"):
            lexical = sum(term in record.content.casefold() or term in record.kind.casefold() for term in terms)
            score = lexical + similarity(query_vector, record.vector or embed(record.content))
            if score:
                ranked.append((score, record))
        return [record for _, record in sorted(ranked, key=lambda item: item[0], reverse=True)[:limit]]

    def relevant(self, query: str, limit: int = 8) -> list[MemoryRecord]:
        """Return semantic-ish vector matches even when terms do not overlap."""
        query_vector = embed(query)
        return [
            record for _, record in sorted(
            ((similarity(query_vector, record.vector or embed(record.content)), record) for record in self.list("active")),
                key=lambda item: item[0],
                reverse=True,
            )[:limit]
        ]

    def relevant_vector(self, vector: list[float], query: str, limit: int = 8) -> list[MemoryRecord]:
        """Hybrid lexical and provider-vector retrieval for active memories."""
        terms = [term.casefold() for term in query.split() if term]
        ranked = []
        for record in self.list("active"):
            semantic = similarity(vector, record.vector or []) if len(record.vector or []) == len(vector) else 0.0
            lexical = sum(term in record.content.casefold() for term in terms)
            ranked.append((semantic + lexical * 0.15, record))
        return [record for score, record in sorted(ranked, key=lambda item: item[0], reverse=True)[:limit] if score > 0]


async def embed_with_provider(texts: list[str], config: dict[str, Any]) -> list[list[float]] | None:
    """Fetch provider embeddings; return None so callers can safely fall back."""
    api_key = os.environ.get(str(config.get("api_key_env", "")))
    if not config.get("enabled") or not api_key or not texts:
        return None
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            response = await client.post(
                str(config.get("base_url", "")).rstrip("/") + "/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": config.get("model", "embedding-3"), "input": texts, "dimensions": config.get("dimensions", 512)},
            )
            response.raise_for_status()
            data = response.json().get("data", [])
            vectors = [item.get("embedding") for item in sorted(data, key=lambda item: item.get("index", 0))]
            return vectors if len(vectors) == len(texts) and all(isinstance(item, list) for item in vectors) else None
    except (httpx.HTTPError, ValueError, TypeError):
        return None
