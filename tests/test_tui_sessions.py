from datetime import timedelta

from mewcode.engine.conversation import ConversationManager
from mewcode.engine.models import Message, MessageRole
from mewcode.tui.app import MewCodeApp
from mewcode.tui.widgets.chat_area import ChatArea


def _saved_sessions(tmp_path):
    manager = ConversationManager(str(tmp_path))
    first = manager.create_conversation("First session")
    manager.add_message(Message(MessageRole.USER, "first question"))
    manager.save_conversation()
    second = manager.create_conversation("Second session")
    manager.add_message(Message(MessageRole.ASSISTANT, "latest answer"))
    second.updated_at = first.updated_at + timedelta(seconds=1)
    manager.save_conversation()
    return first, second


async def test_mount_restores_the_most_recent_saved_session(tmp_path):
    _first, second = _saved_sessions(tmp_path)
    app = MewCodeApp()
    app.conversation_manager = ConversationManager(str(tmp_path))

    async with app.run_test():
        active = app.conversation_manager.get_active_conversation()
        chat = app.query_one("#chat-area", ChatArea)

    assert active is not None
    assert active.id == second.id
    assert any(item["content"] == "latest answer" for item in chat._messages)


async def test_sessions_command_lists_and_resume_switches_session(tmp_path):
    first, second = _saved_sessions(tmp_path)
    app = MewCodeApp()
    app.conversation_manager = ConversationManager(str(tmp_path))

    async with app.run_test() as pilot:
        app._handle_command("/sessions")
        await pilot.pause()
        chat = app.query_one("#chat-area", ChatArea)
        assert first.id[:8] in chat._messages[-1]["content"]
        assert second.id[:8] in chat._messages[-1]["content"]

        app._handle_command(f"/resume {first.id[:8]}")
        await pilot.pause()
        active = app.conversation_manager.get_active_conversation()
        assert active is not None
        assert active.id == first.id
        assert any(item["content"] == "first question" for item in chat._messages)


def test_auto_save_writes_active_session_when_enabled(tmp_path):
    app = MewCodeApp()
    app.conversation_manager = ConversationManager(str(tmp_path))
    app.conversation_manager.create_conversation("Autosave")
    app.conversation_manager.add_message(Message(MessageRole.USER, "persist me"))
    app.config["session"] = {"auto_save": True}

    app._auto_save_active_conversation()

    assert list(tmp_path.glob("*.yaml"))
