from mewcode.engine.models import ApiCallMetrics, MetricsAggregate, TokenUsage


def test_api_call_metrics_calculates_ttft_latency_and_speed():
    metrics = ApiCallMetrics.from_timing(
        usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        started_at=0.0,
        first_token_at=0.5,
        completed_at=2.5,
    )

    assert metrics.prompt_tokens == 10
    assert metrics.completion_tokens == 20
    assert metrics.total_tokens == 30
    assert metrics.ttft_ms == 500
    assert metrics.latency_ms == 2500
    assert metrics.output_tokens_per_second == 10.0


def test_metrics_aggregate_averages_exclude_unavailable_samples():
    aggregate = MetricsAggregate()
    aggregate.add_call(
        ApiCallMetrics(
            output_tokens_per_second=10.0,
            ttft_ms=500,
            latency_ms=1000,
            had_usage=True,
            had_first_token=True,
        )
    )
    aggregate.add_call(ApiCallMetrics(latency_ms=3000))
    aggregate.add_call(
        ApiCallMetrics(
            output_tokens_per_second=30.0,
            ttft_ms=1500,
            latency_ms=3000,
            had_usage=True,
            had_first_token=True,
        )
    )

    assert aggregate.api_call_count == 3
    assert aggregate.usage_call_count == 2
    assert aggregate.average_output_tokens_per_second == 20.0
    assert aggregate.average_ttft_ms == 1000
    assert aggregate.average_latency_ms == 7000 / 3


def test_metrics_aggregate_roundtrip_preserves_sums_and_counts():
    aggregate = MetricsAggregate()
    aggregate.add_call(
        ApiCallMetrics(
            output_tokens_per_second=12.5,
            ttft_ms=250,
            latency_ms=2000,
            had_usage=True,
            had_first_token=True,
        )
    )

    restored = MetricsAggregate.from_dict(aggregate.to_dict())

    assert restored.api_call_count == 1
    assert restored.usage_call_count == 1
    assert restored.average_output_tokens_per_second == 12.5
    assert restored.average_ttft_ms == 250
    assert restored.average_latency_ms == 2000
