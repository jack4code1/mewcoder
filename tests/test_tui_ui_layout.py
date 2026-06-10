import pytest

from mewcode.tui.app import MewCodeApp
from mewcode.tui.widgets.chat_area import ChatArea
from mewcode.tui.widgets.input_box import InputBox
from mewcode.tui.widgets.status_bar import StatusBar


def _child_ids(app: MewCodeApp) -> list[str]:
    layout = app.query_one("#main-layout")
    return [child.id for child in layout.children]


def _assert_chat_visible_and_input_compact(app: MewCodeApp) -> None:
    chat_area = app.query_one("#chat-area", ChatArea)
    input_box = app.query_one("#input-box", InputBox)

    assert chat_area.size.height > 0
    assert input_box.size.height <= 4
    assert chat_area.size.height > input_box.size.height


@pytest.mark.asyncio
async def test_layout_order_chat_status_input():
    app = MewCodeApp()
    async with app.run_test():
        ids = _child_ids(app)
        assert ids.index("chat-area") < ids.index("status-bar")
        assert ids.index("status-bar") < ids.index("input-box")


@pytest.mark.asyncio
async def test_status_bar_hidden_at_startup():
    app = MewCodeApp()
    async with app.run_test():
        status_bar = app.query_one("#status-bar", StatusBar)
        assert status_bar.is_visible is False
        assert status_bar.has_class("hidden")


@pytest.mark.asyncio
async def test_typing_shows_status_bar():
    app = MewCodeApp()
    async with app.run_test() as pilot:
        input_field = app.query_one("#input-field")
        status_bar = app.query_one("#status-bar", StatusBar)

        input_field.value = "hello"
        await pilot.pause(0.1)

        assert status_bar.is_visible is True
        assert not status_bar.has_class("hidden")


@pytest.mark.asyncio
async def test_clearing_hides_status_bar():
    app = MewCodeApp()
    async with app.run_test() as pilot:
        input_field = app.query_one("#input-field")
        status_bar = app.query_one("#status-bar", StatusBar)

        input_field.value = "hello"
        await pilot.pause(0.1)
        assert status_bar.is_visible is True

        input_field.value = ""
        await pilot.pause(0.1)
        assert status_bar.is_visible is False
        assert status_bar.has_class("hidden")


@pytest.mark.asyncio
async def test_submit_clears_input_and_hides_status_bar():
    app = MewCodeApp()
    async with app.run_test() as pilot:
        input_field = app.query_one("#input-field")
        status_bar = app.query_one("#status-bar", StatusBar)

        input_field.value = "a question"
        input_field.focus()
        await pilot.pause(0.1)
        assert status_bar.is_visible is True

        await pilot.press("enter")
        await pilot.pause(0.1)

        assert input_field.value == ""
        assert status_bar.is_visible is False


@pytest.mark.asyncio
async def test_input_box_keeps_at_least_one_line():
    app = MewCodeApp()
    async with app.run_test(size=(80, 12)):
        input_box = app.query_one("#input-box", InputBox)
        # Border (top+bottom = 2) plus at least one content row.
        assert input_box.styles.min_height is not None
        assert input_box.styles.min_height.value >= 3
        # The widget actually renders with room for a content line.
        assert input_box.size.height >= 3


@pytest.mark.asyncio
async def test_hidden_status_bar_gives_chat_more_height():
    app = MewCodeApp()
    async with app.run_test(size=(120, 24)) as pilot:
        chat_area = app.query_one("#chat-area", ChatArea)
        status_bar = app.query_one("#status-bar", StatusBar)
        input_field = app.query_one("#input-field")

        hidden_chat_height = chat_area.size.height
        assert status_bar.is_visible is False

        input_field.value = "typing"
        await pilot.pause(0.1)
        assert status_bar.is_visible is True
        shown_chat_height = chat_area.size.height

        # When the status bar appears it occupies a row, so the chat area
        # shrinks; hidden state gives the chat area more height.
        assert hidden_chat_height >= shown_chat_height


@pytest.mark.asyncio
async def test_chat_area_visible_at_startup_desktop():
    app = MewCodeApp()
    async with app.run_test(size=(120, 30)):
        _assert_chat_visible_and_input_compact(app)


@pytest.mark.asyncio
async def test_chat_area_visible_at_startup_medium():
    app = MewCodeApp()
    async with app.run_test(size=(100, 20)):
        _assert_chat_visible_and_input_compact(app)


@pytest.mark.asyncio
async def test_chat_area_visible_at_startup_small():
    app = MewCodeApp()
    async with app.run_test(size=(80, 12)):
        chat_area = app.query_one("#chat-area", ChatArea)
        input_box = app.query_one("#input-box", InputBox)

        assert chat_area.size.height > 0
        assert 3 <= input_box.size.height <= 4


@pytest.mark.asyncio
async def test_typing_status_bar_does_not_collapse_chat():
    app = MewCodeApp()
    async with app.run_test(size=(120, 30)) as pilot:
        input_field = app.query_one("#input-field")
        status_bar = app.query_one("#status-bar", StatusBar)

        input_field.value = "typing"
        await pilot.pause(0.1)

        assert status_bar.is_visible is True
        _assert_chat_visible_and_input_compact(app)


@pytest.mark.asyncio
async def test_typed_input_text_is_rendered():
    app = MewCodeApp()
    async with app.run_test(size=(100, 20)) as pilot:
        input_field = app.query_one("#input-field")
        input_field.focus()

        await pilot.press("v", "i", "s", "i", "b", "l", "e")
        await pilot.pause(0.1)

        assert input_field.value == "visible"
        assert "visible" in app.export_screenshot()


@pytest.mark.asyncio
async def test_prompt_label_aligns_with_input_field():
    app = MewCodeApp()
    async with app.run_test(size=(100, 20)):
        prompt = app.query_one("#prompt")
        input_field = app.query_one("#input-field")

        assert prompt.region.y == input_field.region.y
        assert prompt.region.height == input_field.region.height


@pytest.mark.asyncio
async def test_chat_area_displays_system_message_at_startup():
    app = MewCodeApp()
    async with app.run_test(size=(100, 20)):
        chat_area = app.query_one("#chat-area", ChatArea)
        scroll = app.query_one("#chat-scroll")

        assert chat_area.size.height > 0
        assert len(scroll.children) >= 1
        assert any(
            msg["role"] == "system" and "Welcome to MewCode" in msg["content"]
            for msg in chat_area._messages
        )


@pytest.mark.asyncio
async def test_streaming_output_visible_in_chat_area():
    app = MewCodeApp()
    async with app.run_test(size=(100, 20)):
        chat_area = app.query_one("#chat-area", ChatArea)

        chat_area.add_assistant_message_start()
        chat_area.add_stream_chunk("hello")

        assert chat_area.size.height > 0
        assert chat_area._stream_widget_id is not None
        assert app.query_one(f"#{chat_area._stream_widget_id}") is not None


@pytest.mark.asyncio
async def test_submit_keeps_chat_area_visible():
    async def noop_process(_content: str) -> None:
        return None

    app = MewCodeApp()
    app._process_with_llm = noop_process

    async with app.run_test(size=(100, 20)) as pilot:
        input_field = app.query_one("#input-field")
        chat_area = app.query_one("#chat-area", ChatArea)

        input_field.value = "a visible question"
        input_field.focus()
        await pilot.pause(0.1)

        await pilot.press("enter")
        await pilot.pause(0.1)

        assert chat_area.size.height > 0
        assert any(
            msg["role"] == "user" and msg["content"] == "a visible question"
            for msg in chat_area._messages
        )
