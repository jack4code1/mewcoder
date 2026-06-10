import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input

from mewcode.tui.widgets.input_box import InputBox, InputContentChanged, InputSubmitted


class InputBoxTestApp(App):
    def __init__(self):
        super().__init__()
        self.submitted: list[str] = []
        self.changed: list[bool] = []

    def compose(self) -> ComposeResult:
        yield InputBox(id="input-box")

    def on_input_submitted(self, event: InputSubmitted) -> None:
        self.submitted.append(event.value)

    def on_input_content_changed(self, event: InputContentChanged) -> None:
        self.changed.append(event.has_content)


async def _submit(input_field: Input, pilot, value: str) -> None:
    input_field.value = value
    input_field.focus()
    await pilot.press("enter")
    await pilot.pause(0.1)


@pytest.mark.asyncio
async def test_enter_submits_and_clears_input():
    app = InputBoxTestApp()
    async with app.run_test() as pilot:
        input_box = app.query_one("#input-box", InputBox)
        input_field = app.query_one("#input-field", Input)

        await _submit(input_field, pilot, "hello")

        assert app.submitted == ["hello"]
        assert input_box.history == ["hello"]
        assert input_box.history_index == 1
        assert input_field.value == ""


@pytest.mark.asyncio
async def test_empty_enter_does_not_add_history():
    app = InputBoxTestApp()
    async with app.run_test() as pilot:
        input_box = app.query_one("#input-box", InputBox)
        input_field = app.query_one("#input-field", Input)

        await _submit(input_field, pilot, "   ")

        assert app.submitted == []
        assert input_box.history == []
        assert input_field.value == "   "


@pytest.mark.asyncio
async def test_up_down_navigates_prompt_history():
    app = InputBoxTestApp()
    async with app.run_test() as pilot:
        input_field = app.query_one("#input-field", Input)

        await _submit(input_field, pilot, "first")
        await _submit(input_field, pilot, "second")

        input_field.focus()
        await pilot.press("up")
        assert input_field.value == "second"

        await pilot.press("up")
        assert input_field.value == "first"

        await pilot.press("down")
        assert input_field.value == "second"

        await pilot.press("down")
        assert input_field.value == ""


@pytest.mark.asyncio
async def test_typing_broadcasts_input_changed_has_content():
    app = InputBoxTestApp()
    async with app.run_test() as pilot:
        input_field = app.query_one("#input-field", Input)
        input_field.value = "hello"
        await pilot.pause(0.1)

        assert app.changed
        assert app.changed[-1] is True


@pytest.mark.asyncio
async def test_clearing_broadcasts_input_changed_empty():
    app = InputBoxTestApp()
    async with app.run_test() as pilot:
        input_field = app.query_one("#input-field", Input)
        input_field.value = "hello"
        await pilot.pause(0.1)
        input_field.value = ""
        await pilot.pause(0.1)

        assert app.changed[-1] is False


@pytest.mark.asyncio
async def test_submit_clears_and_signals_empty():
    app = InputBoxTestApp()
    async with app.run_test() as pilot:
        input_field = app.query_one("#input-field", Input)

        await _submit(input_field, pilot, "hello")

        assert app.submitted == ["hello"]
        assert input_field.value == ""
        # Clearing on submit must produce a final has_content=False signal.
        assert app.changed[-1] is False

