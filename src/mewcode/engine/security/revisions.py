"""Project-local pre-write revisions for review and user-initiated rollback."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4


@dataclass
class Revision:
    id: str
    path: str
    existed: bool
    content: str = ""


class RevisionStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.path = self.workspace / ".mewcode" / "revisions.json"

    def list(self) -> list[Revision]:
        if not self.path.exists():
            return []
        return [Revision(**item) for item in json.loads(self.path.read_text(encoding="utf-8"))]

    def capture(self, path: Path) -> Revision:
        revision = Revision(uuid4().hex, str(path), path.exists(), path.read_text(encoding="utf-8", errors="replace") if path.is_file() else "")
        revisions = self.list() + [revision]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(item) for item in revisions]), encoding="utf-8")
        return revision

    def get(self, revision_id: str) -> Revision | None:
        return next((item for item in self.list() if item.id == revision_id), None)

    def rollback(self, revision_id: str) -> Revision | None:
        revision = self.get(revision_id)
        if revision is None:
            return None
        path = Path(revision.path)
        if revision.existed:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(revision.content, encoding="utf-8")
        elif path.exists():
            path.unlink()
        return revision
