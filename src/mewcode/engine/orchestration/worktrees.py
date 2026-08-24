from dataclasses import dataclass, field
from pathlib import Path
import subprocess
from uuid import uuid4


@dataclass(frozen=True)
class WorktreeLease:
    path: Path
    branch: str
    base_revision: str
    task_id: str


@dataclass
class WorktreeManager:
    workspace: Path
    leases: dict[str, WorktreeLease] = field(default_factory=dict)

    def _git(self, *args: str) -> str:
        result = subprocess.run(["git", *args], cwd=self.workspace, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "git command failed")
        return result.stdout.strip()

    def create(self, task_id: str, root: Path | None = None) -> WorktreeLease:
        self._git("rev-parse", "--is-inside-work-tree")
        if self._git("status", "--porcelain"):
            raise RuntimeError("main worktree is dirty")
        base = self._git("rev-parse", "HEAD")
        branch = f"mewcode/{task_id[:12]}-{uuid4().hex[:6]}"
        path = (root or self.workspace.parent / ".mewcode-worktrees") / branch.replace("/", "-")
        self._git("worktree", "add", "-b", branch, str(path))
        lease = WorktreeLease(path.resolve(), branch, base, task_id)
        self.leases[task_id] = lease
        return lease

    def diff(self, task_id: str) -> str:
        lease = self.leases[task_id]
        return self._git("-C", str(lease.path), "diff", lease.base_revision)

    def cleanup(self, task_id: str) -> None:
        lease = self.leases.pop(task_id, None)
        if lease is None:
            raise ValueError("unknown managed worktree")
        self._git("worktree", "remove", str(lease.path))
