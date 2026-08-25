import asyncio
import subprocess

import pytest

from mewcode.engine.orchestration import TaskRunner, TaskSpec, TeamCoordinator, WorktreeManager


def _git_repo(path):
    for args in (("init",), ("config", "user.email", "test@example.com"), ("config", "user.name", "Test")):
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)
    (path / "base.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, check=True, capture_output=True)


@pytest.mark.asyncio
async def test_isolated_task_collects_diff_and_cleans_worktree(tmp_path):
    _git_repo(tmp_path)
    manager = WorktreeManager(tmp_path)

    async def worker(spec, lease):
        (lease.path / "base.txt").write_text("changed\n", encoding="utf-8")
        return spec.objective

    run = await TaskRunner().run_isolated(TaskSpec("change file"), manager, worker)

    assert run.status == "completed"
    assert "-base" in run.diff and "+changed" in run.diff
    assert not manager.leases
    assert not (tmp_path.parent / ".mewcode-worktrees").exists() or not any((tmp_path.parent / ".mewcode-worktrees").iterdir())


@pytest.mark.asyncio
async def test_team_bounds_concurrency_and_rejects_conflicts():
    active = peak = 0

    async def worker(spec):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return spec.objective

    team = TeamCoordinator(max_concurrency=1)
    runs = await team.run_all([TaskSpec("a", ["a"]), TaskSpec("b", ["b"])], worker)
    assert [run.status for run in runs] == ["completed", "completed"]
    assert peak == 1
    with pytest.raises(ValueError, match="conflicts"):
        await team.run_all([TaskSpec("a", ["same"]), TaskSpec("b", ["same"])], worker)


@pytest.mark.asyncio
async def test_kept_task_diff_can_be_applied_then_cleans_worktree(tmp_path):
    _git_repo(tmp_path)
    manager = WorktreeManager(tmp_path)

    async def worker(spec, lease):
        (lease.path / "base.txt").write_text("applied\n", encoding="utf-8")
        return "done"

    run = await TaskRunner().run_isolated(TaskSpec("apply"), manager, worker, keep_worktree=True)
    assert run.id in manager.leases
    manager.apply(run.id)

    assert (tmp_path / "base.txt").read_text() == "applied\n"
    assert not manager.leases
