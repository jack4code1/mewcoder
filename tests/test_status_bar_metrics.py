from mewcode.engine.models import ApiCallMetrics, MetricsAggregate, MetricsSnapshot, TokenUsage
from mewcode.tui.widgets.status_bar import StatusBar


def test_status_bar_formats_real_token_usage_without_fake_total():
    bar = StatusBar()

    bar.update_token_usage(
        TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    )

    assert bar.token_usage == "30 P:10 C:20"
    assert "/0" not in bar._format_status(width=120)


def test_status_bar_formats_average_metrics():
    aggregate = MetricsAggregate()
    aggregate.add_call(
        ApiCallMetrics(
            output_tokens_per_second=10.0,
            ttft_ms=500,
            latency_ms=2500,
            had_usage=True,
            had_first_token=True,
        )
    )
    bar = StatusBar()

    bar.update_metrics(
        MetricsSnapshot(
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            api_metrics=aggregate,
        )
    )

    formatted = bar._format_status(width=160)
    assert "10.0 tok/s" in formatted
    assert "TTFT: 500ms" in formatted
    assert "Lat: 2.5s" in formatted
    assert "30 P:10 C:20" in formatted


def test_status_bar_narrow_format_hides_working_dir():
    aggregate = MetricsAggregate()
    aggregate.add_call(
        ApiCallMetrics(
            output_tokens_per_second=18.6,
            ttft_ms=520,
            latency_ms=2400,
            had_usage=True,
            had_first_token=True,
        )
    )
    bar = StatusBar()
    bar.update_model("gpt-4o-mini")
    bar.working_dir = r"E:\very\long\project\path"
    bar.update_metrics(
        MetricsSnapshot(
            token_usage=TokenUsage(
                prompt_tokens=820,
                completion_tokens=420,
                total_tokens=1240,
            ),
            api_metrics=aggregate,
        )
    )

    formatted = bar._format_status(width=60)

    assert "gpt-4o-mini" in formatted
    assert "Tok: 1.2k" in formatted
    assert "18.6 tok/s" in formatted
    assert "Idle" in formatted
    assert "very\\long" not in formatted
