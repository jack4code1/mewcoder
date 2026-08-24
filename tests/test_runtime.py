from mewcode.engine.runtime import ProjectRuntime


def test_project_runtime_resolves_workspace_and_keeps_permissions_isolated(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    runtime = ProjectRuntime(first)
    runtime.permissions.grant_project("Bash")
    runtime.permissions.save_project(first)

    other = ProjectRuntime(second)

    assert runtime.workspace == first.resolve()
    assert runtime.permissions.allows("Bash")
    assert not other.permissions.allows("Bash")
