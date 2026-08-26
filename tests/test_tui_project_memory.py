from mewcode.engine.context import MemoryRecord, ProjectMemoryStore
from mewcode.engine.models import Message, MessageRole
from mewcode.tui.app import MewCodeApp
from mewcode.tui.widgets.chat_area import ChatArea


async def test_memory_command_displays_record_id_kind_and_content(tmp_path):
    app = MewCodeApp()
    app.memory_store = ProjectMemoryStore(tmp_path)
    record = app.memory_store.save(MemoryRecord("Use pytest", kind="preference"))

    async with app.run_test() as pilot:
        app._handle_command("/memory")
        await pilot.pause()
        chat = app.query_one("#chat-area", ChatArea)

    assert record.id in chat._messages[-1]["content"]
    assert "[preference]: Use pytest" in chat._messages[-1]["content"]


def test_project_memory_precedes_conversation_history(tmp_path):
    app = MewCodeApp()
    app.memory_store = ProjectMemoryStore(tmp_path)
    app.memory_store.save(MemoryRecord("Repository uses pytest"))
    app.conversation_manager.create_conversation()
    app.conversation_manager.add_message(Message(MessageRole.USER, "What tests run?"))

    messages = app._messages_with_system()

    assert messages[0].role is MessageRole.SYSTEM
    assert messages[1].content == "Project memory (fact): Repository uses pytest"
    assert messages[2].content.startswith("Structured session state")
    assert messages[3].role is MessageRole.USER


def test_memory_search_ranks_matching_records(tmp_path):
    store = ProjectMemoryStore(tmp_path)
    store.save(MemoryRecord("Use pytest for Python tests"))
    store.save(MemoryRecord("Use npm for frontend"))

    assert [record.content for record in store.search("python pytest")] == ["Use pytest for Python tests"]


def test_pending_memory_requires_approval_before_retrieval(tmp_path):
    store = ProjectMemoryStore(tmp_path)
    candidate = store.save(MemoryRecord("Use ruff before commit", status="pending", source="auto"))

    assert store.relevant("ruff").__eq__([])
    assert store.approve(candidate.id) is not None
    assert store.relevant("ruff")[0].id == candidate.id


async def test_summarize_command_replaces_older_history():
    app = MewCodeApp()
    async with app.run_test() as pilot:
        for index in range(10):
            app.conversation_manager.add_message(Message(MessageRole.USER, f"message {index}"))
        app._handle_command("/summarize")
        await pilot.pause()

    messages = app.conversation_manager.get_messages()
    assert messages[0].role is MessageRole.SYSTEM
    assert "Historical summary schema v1" in messages[0].content
    assert len(messages) == 9
