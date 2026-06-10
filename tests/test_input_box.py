import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input

from mewcode.tui.widgets.input_box import InputBox, InputSubmitted


class InputBoxTestApp(App):
    def __init__(self):
        super().__init__()
        self.submitted: list[str] = []

    def compose(self) -> ComposeResult:
        yield InputBox(id="input-box")

    def on_input_submitted(self, event: InputSubmitted) -> None:
        self.submitted.append(event.value)


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
