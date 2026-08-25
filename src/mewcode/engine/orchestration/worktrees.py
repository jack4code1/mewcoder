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
        result = subprocess.run(
            ["git", "-C", str(lease.path), "diff", lease.base_revision],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "git diff failed")
        return result.stdout

    def cleanup(self, task_id: str) -> None:
        lease = self.leases.pop(task_id, None)
        if lease is None:
            raise ValueError("unknown managed worktree")
        # Leases are disposable task worktrees; their diff is collected before cleanup.
        self._git("worktree", "remove", "--force", str(lease.path))

    def apply(self, task_id: str) -> str:
        """Apply a managed task diff to its clean source worktree, then clean up."""
        lease = self.leases.get(task_id)
        if lease is None:
            raise ValueError("unknown managed worktree")
        if self._git("status", "--porcelain"):
            raise RuntimeError("main worktree is dirty")
        diff = self.diff(task_id)
        if not diff:
            self.cleanup(task_id)
            return ""
        result = subprocess.run(["git", "apply", "--whitespace=nowarn", "-"], cwd=self.workspace, input=diff, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "could not apply task diff")
        self.cleanup(task_id)
        return diff
