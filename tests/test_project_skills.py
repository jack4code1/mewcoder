from mewcode.engine.extensions import ProjectSkillStore
from mewcode.tui.app import MewCodeApp
from mewcode.tui.widgets.chat_area import ChatArea


def test_project_skill_store_discovers_nonempty_markdown_files(tmp_path):
    skills_dir = tmp_path / ".mewcode" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "python.md").write_text("Use pytest.", encoding="utf-8")
    (skills_dir / "empty.md").write_text("\n", encoding="utf-8")

    skills = ProjectSkillStore(tmp_path).list()

    assert [(skill.name, skill.instructions) for skill in skills] == [("python", "Use pytest.")]


def test_project_skill_store_save_and_delete_rejects_unsafe_names(tmp_path):
    store = ProjectSkillStore(tmp_path)
    assert store.save("python_tools", "Use pytest.").name == "python_tools"
    assert store.delete("python_tools") is True
    try:
        store.save("../escape", "bad")
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe name was accepted")


async def test_skills_command_and_request_context(tmp_path):
    skills_dir = tmp_path / ".mewcode" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "repo.md").write_text("Run focused tests first.", encoding="utf-8")
    app = MewCodeApp()
    app.skill_store = ProjectSkillStore(tmp_path)

    messages = app._messages_with_system()
    assert messages[1].content.endswith("Run focused tests first.")

    async with app.run_test() as pilot:
        app._handle_command("/skills")
        await pilot.pause()
        chat = app.query_one("#chat-area", ChatArea)

    assert "repo:" in chat._messages[-1]["content"]
