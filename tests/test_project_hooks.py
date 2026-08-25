import pytest

from mewcode.engine.extensions import ProjectHookStore
from mewcode.engine.security.gateway import ExecutionGateway
from mewcode.engine.tools import ToolContext, ToolRegistry


def test_project_hook_store_ignores_missing_config(tmp_path):
    assert ProjectHookStore(tmp_path).definitions() == []


@pytest.mark.asyncio
async def test_hook_requires_bash_authorization(tmp_path):
    config = tmp_path / ".mewcode" / "hooks.yaml"
    config.parent.mkdir()
    config.write_text("hooks:\n  - event: task_start\n    name: check\n    command: echo check\n", encoding="utf-8")
    registry = ToolRegistry(ToolContext.detect(tmp_path))
    runner = ProjectHookStore(tmp_path).build_runner(ExecutionGateway(registry))

    results = await runner.run("task_start")

    assert results[0].success is False
    assert "Approval required" in results[0].message
