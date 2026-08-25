import pytest

from mewcode.engine.security.gateway import ExecutionGateway
from mewcode.engine.security.models import ExecutionRequest, OperationKind
from mewcode.engine.security.revisions import RevisionStore
from mewcode.engine.tools import ToolContext, ToolRegistry, WriteFileTool


@pytest.mark.asyncio
async def test_gateway_captures_and_rolls_back_existing_file(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("before", encoding="utf-8")
    registry = ToolRegistry(ToolContext.detect(tmp_path))
    registry.register(WriteFileTool())
    gateway = ExecutionGateway(registry, revisions=RevisionStore(tmp_path))
    gateway.grants.grant("WriteFile")

    result = await gateway.execute(ExecutionRequest("WriteFile", {"path": "file.txt", "content": "after"}, operation=OperationKind.WRITE))
    revision = gateway.revisions.rollback(result.metadata["revision_id"])

    assert revision is not None
    assert path.read_text() == "before"


@pytest.mark.asyncio
async def test_rollback_removes_file_created_by_write(tmp_path):
    registry = ToolRegistry(ToolContext.detect(tmp_path))
    registry.register(WriteFileTool())
    gateway = ExecutionGateway(registry, revisions=RevisionStore(tmp_path))
    gateway.grants.grant("WriteFile")
    result = await gateway.execute(ExecutionRequest("WriteFile", {"path": "new.txt", "content": "new"}, operation=OperationKind.WRITE))

    gateway.revisions.rollback(result.metadata["revision_id"])
    assert not (tmp_path / "new.txt").exists()
