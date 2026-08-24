from datetime import datetime, timedelta, timezone

from mewcode.engine.security import (
    ExecutionRequest,
    OperationKind,
    PermissionDecision,
    PermissionStore,
    decide,
)


def test_read_is_allowed_by_default():
    request = ExecutionRequest("ReadFile", {}, operation=OperationKind.READ)
    assert decide(request) is PermissionDecision.ALLOW


def test_write_requires_approval_until_explicitly_granted():
    request = ExecutionRequest("WriteFile", {}, operation=OperationKind.WRITE)
    grants = PermissionStore()
    assert decide(request, grants) is PermissionDecision.REQUIRE_APPROVAL
    grants.grant("WriteFile")
    assert decide(request, grants) is PermissionDecision.ALLOW
    grants.revoke("WriteFile")
    assert decide(request, grants) is PermissionDecision.REQUIRE_APPROVAL


def test_project_grants_persist_within_workspace(tmp_path):
    first = PermissionStore()
    first.grant_project("Bash")
    first.save_project(tmp_path)

    restored = PermissionStore()
    restored.load_project(tmp_path)

    assert restored.allows("Bash")
    restored.revoke_project("Bash")
    restored.save_project(tmp_path)

    after_revoke = PermissionStore()
    after_revoke.load_project(tmp_path)
    assert not after_revoke.allows("Bash")


def test_project_grant_does_not_follow_store_to_another_workspace(tmp_path):
    first_project = tmp_path / "first"
    second_project = tmp_path / "second"
    first_project.mkdir()
    second_project.mkdir()
    grants = PermissionStore()
    grants.load_project(first_project)
    grants.grant_project("Bash")
    grants.save_project(first_project)

    grants.load_project(second_project)

    assert not grants.allows("Bash")


def test_one_time_grant_is_consumed_after_matching_request():
    request = ExecutionRequest("WriteFile", {}, operation=OperationKind.WRITE)
    grants = PermissionStore()
    grants.grant_once("WriteFile")

    assert decide(request, grants) is PermissionDecision.ALLOW
    assert decide(request, grants) is PermissionDecision.REQUIRE_APPROVAL


def test_expired_session_grant_is_not_allowed():
    request = ExecutionRequest("Bash", {}, operation=OperationKind.COMMAND)
    grants = PermissionStore()
    grants.grant("Bash", expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))

    assert decide(request, grants) is PermissionDecision.REQUIRE_APPROVAL
