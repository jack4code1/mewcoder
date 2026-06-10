from mewcode.engine.agent_events import AgentEvent, AgentEventType, AgentStopReason
from mewcode.engine.models import ApiCallMetrics, MetricsAggregate, MetricsSnapshot, TokenUsage


def test_stream_text_event():
    event = AgentEvent.stream_text("hello")

    assert event.event_type == AgentEventType.STREAM_TEXT
    assert event.text == "hello"


def test_tool_use_event_payload():
    event = AgentEvent.tool_use(
        "call_1",
        "ReadFile",
        {"path": "a.py"},
        "a.py",
    )

    assert event.event_type == AgentEventType.TOOL_USE
    assert event.tool_call_id == "call_1"
    assert event.tool_name == "ReadFile"
    assert event.tool_input == {"path": "a.py"}
    assert event.summary == "a.py"


def test_loop_complete_event_payload():
    event = AgentEvent.loop_complete(3, AgentStopReason.MODEL_DONE)

    assert event.event_type == AgentEventType.LOOP_COMPLETE
    assert event.total_turns == 3
    assert event.stop_reason == AgentStopReason.MODEL_DONE


def test_usage_event_payload():
    usage = TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    event = AgentEvent.usage(usage)

    assert event.event_type == AgentEventType.USAGE
    assert event.usage == usage


def test_metrics_event_payload():
    aggregate = MetricsAggregate()
    call = ApiCallMetrics(ttft_ms=500, latency_ms=2500)
    aggregate.add_call(call)
    usage = TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    snapshot = MetricsSnapshot(
        token_usage=usage,
        api_metrics=aggregate,
        last_call=call,
    )

    event = AgentEvent.metrics(snapshot)

    assert event.event_type == AgentEventType.METRICS
    assert event.usage == usage
    assert event.metrics_snapshot == snapshot
    assert event.api_call_metrics == call
