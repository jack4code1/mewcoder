import pytest

from mewcode.engine.models import StreamChunk, TokenUsage
from mewcode.tui.app import MewCodeApp
from mewcode.tui.widgets.status_bar import StatusBar


class FakeClient:
    def __init__(self, streams):
        self.streams = streams
        self.calls = 0

    async def chat_stream(self, messages, tools=None, **kwargs):
        stream = self.streams[self.calls]
        self.calls += 1
        for chunk in stream:
            yield chunk

    async def close(self):
        return None


async def _run_message(app: MewCodeApp, pilot, content: str) -> None:
    app._handle_message(content)
    for _ in range(30):
        await pilot.pause(0.1)
        if not app.is_processing:
            break


@pytest.mark.asyncio
async def test_status_bar_is_visible_in_main_layout():
    app = MewCodeApp()
    async with app.run_test():
        status_bar = app.query_one("#status-bar", StatusBar)

        assert status_bar.parent is app.query_one("#main-layout")
        assert "Tok:" in status_bar._format_status(width=120)
        assert "Avg:" in status_bar._format_status(width=120)


@pytest.mark.asyncio
async def test_tui_updates_status_bar_from_usage_and_metrics_events():
    app = MewCodeApp()
    async with app.run_test() as pilot:
        app.llm_client = FakeClient(
            [
                [
                    StreamChunk(content="hello", model="fake"),
                    StreamChunk(
                        content="",
                        model="fake",
                        finish_reason="stop",
                        token_usage=TokenUsage(
                            prompt_tokens=10,
                            completion_tokens=20,
                            total_tokens=30,
                        ),
                    ),
                ]
            ]
        )

        await _run_message(app, pilot, "measure")
        status_bar = app.query_one("#status-bar", StatusBar)

    assert status_bar.token_usage == "30 P:10 C:20"
    assert "Lat:" in status_bar.performance_metrics
