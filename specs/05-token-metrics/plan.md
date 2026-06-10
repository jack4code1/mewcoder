# MewCode Token Metrics Plan

## Scope Decision

This plan implements the token and API metrics feature requested for P0, P1, and P2. It does not start implementation until the four documents in `specs/05-token-metrics/` are approved.

The implementation should be incremental:

1. Fix correctness of token usage data.
2. Add engine-level metrics data and events.
3. Wire the TUI status bar to the real data.
4. Persist metrics to session YAML.
5. Improve narrow terminal rendering.

## Current Evidence

- `src/mewcode/engine/agent.py` already accumulates `TokenUsage` from stream chunks and emits `AgentEvent.usage(total_usage)`.
- `src/mewcode/tui/app.py` currently calls `status_bar.update_token_usage(event.usage.total_tokens, 0)`, which makes the status bar show a real total beside a fake `0`.
- `src/mewcode/tui/widgets/status_bar.py` currently stores `token_usage` as a string and renders `[Tokens: {used}/{total}]`.
- `src/mewcode/engine/models/message.py` defines `TokenUsage`, `Message.token_usage`, `LLMResponse.token_usage`, and `StreamChunk.token_usage`.
- `Message.to_dict()` currently serializes tool metadata but not `token_usage`.
- `Message.from_dict()` currently restores tool metadata but not `token_usage`.
- `src/mewcode/engine/conversation.py` persists aggregate `total_token_usage` and restores it from YAML.
- `src/mewcode/engine/adapters/openai_adapter.py` parses streaming usage only when a streamed data object contains `usage`.
- `src/mewcode/engine/adapters/custom_adapter.py` returns an empty `TokenUsage()` in streaming, which can be mistaken for a real zero.
- `src/mewcode/engine/adapters/claude_adapter.py` maps Anthropic `input_tokens` and `output_tokens` into `TokenUsage`.
- `src/mewcode/engine/adapters/ollama_adapter.py` maps available prompt and generation token counters into `TokenUsage`.

## Architecture

Add protocol-neutral metrics models in the engine layer. The TUI should receive already-normalized data and only format it.

Candidate new or updated modules:

- `src/mewcode/engine/models/metrics.py`: metric dataclasses and aggregation helpers.
- `src/mewcode/engine/models/__init__.py`: exports metric models.
- `src/mewcode/engine/agent_events.py`: add a metrics payload or a dedicated metrics event.
- `src/mewcode/engine/agent.py`: measure model call timing and emit metrics snapshots.
- `src/mewcode/engine/conversation.py`: persist and restore aggregate metrics.
- `src/mewcode/engine/models/message.py`: serialize and deserialize message-level `token_usage`.
- `src/mewcode/engine/adapters/openai_adapter.py`: request and parse streaming usage consistently.
- `src/mewcode/engine/adapters/custom_adapter.py`: request usage for OpenAI-compatible endpoints where possible and stop emitting fake zero usage.
- `src/mewcode/engine/adapters/claude_adapter.py`: verify streamed usage normalization.
- `src/mewcode/engine/adapters/ollama_adapter.py`: verify streamed usage normalization.
- `src/mewcode/tui/app.py`: consume usage and metrics events.
- `src/mewcode/tui/widgets/status_bar.py`: display tokens, speed, TTFT, latency, and narrow variants.

## Data Model

Add a per-call metrics type. Exact names can change during implementation, but the fields should represent:

```python
ApiCallMetrics:
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    ttft_ms: Optional[int]
    latency_ms: Optional[int]
    output_tokens_per_second: Optional[float]
    started_at: Optional[str]
    completed_at: Optional[str]
    had_usage: bool
    had_first_token: bool
```

Add an aggregate metrics type:

```python
MetricsAggregate:
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    api_call_count: int
    usage_call_count: int
    speed_sample_count: int
    ttft_sample_count: int
    latency_sample_count: int
    output_tokens_per_second_sum: float
    ttft_ms_sum: int
    latency_ms_sum: int
```

The aggregate exposes computed properties:

- `average_output_tokens_per_second`.
- `average_ttft_ms`.
- `average_latency_ms`.

Use sample counts so averages do not treat unavailable metrics as zero.

## Agent Event Design

Extend `AgentEvent` without breaking existing event consumers.

Acceptable approaches:

- Add `metrics: Optional[MetricsSnapshot]` to `AgentEvent` and keep `AgentEventType.USAGE`.
- Or add `AgentEventType.METRICS` and emit metrics snapshots separately.

The event payload should include:

- cumulative token usage.
- current call metrics when a call completes.
- aggregate average speed.
- aggregate average TTFT.
- aggregate average latency.
- number of API calls represented by the aggregate.

Existing tests for `usage` events should continue to pass or be updated with equivalent coverage.

## Timing Strategy

Use `time.monotonic()` or an injectable clock.

Per model turn:

1. Record `request_start` immediately before calling `chat_stream`.
2. Initialize `first_token_time` as unavailable.
3. For every streamed chunk:
   - If the chunk has non-empty `content` and `first_token_time` is unavailable, record current time.
   - Accumulate token usage if `chunk.token_usage` exists and represents real provider usage.
   - Continue emitting stream text events without waiting for metrics.
4. Record `request_end` after the async stream finishes.
5. Compute:
   - `ttft_ms = first_token_time - request_start` if first token exists.
   - `latency_ms = request_end - request_start`.
   - `output_duration = request_end - first_token_time` if first token exists.
   - `tok/s = completion_tokens / output_duration` if completion tokens and output duration are positive.
6. Update the conversation metrics aggregate.
7. Emit a metrics or usage event.

If the provider returns usage only in a final empty chunk, this still works because token usage is accumulated independently from text chunks.

## Token Usage Semantics

Avoid conflating unavailable usage with zero usage.

Rules:

- `None` means usage is unavailable for this chunk or call.
- `TokenUsage(0, 0, 0)` means the provider explicitly returned zero values or a test intentionally created zero usage.
- Adapter code should not create `TokenUsage()` as a placeholder for missing usage.
- The Agent Loop should aggregate only real `TokenUsage` values.
- The UI should display `N/A` for unavailable values.

This may require a helper such as `has_reported_usage(chunk)` or a richer usage wrapper if current `TokenUsage` alone cannot distinguish placeholder zeros.

## Adapter Plan

### OpenAI-compatible streaming

For OpenAI-compatible chat completions, include streaming usage where supported:

```json
"stream_options": {
  "include_usage": true
}
```

Then parse final streamed usage objects and yield a `StreamChunk` with `token_usage`.

The implementation should be tolerant:

- If an endpoint rejects `stream_options`, document or handle the provider limitation.
- If an endpoint does not send usage, yield no token usage.
- Existing content and tool-call streaming must not regress.

### Custom adapter

For custom OpenAI-compatible endpoints:

- Use the same usage request option when the configured API format is OpenAI-compatible.
- Do not emit `TokenUsage()` just to satisfy a field.
- Parse non-streaming and streaming usage consistently.

For generic custom endpoints:

- Parse usage only when the response schema contains a clear usage object.
- Otherwise report unavailable usage.

### Claude adapter

Confirm streamed Anthropic events map:

- input tokens from message start or equivalent event.
- output tokens from message delta or equivalent event.
- total as input plus output when both are known.

Avoid double-counting partial updates if Anthropic sends cumulative counters.

### Ollama adapter

Confirm final streamed counters map:

- prompt token count to `prompt_tokens`.
- generation token count to `completion_tokens`.
- total as prompt plus completion when both exist.

Avoid reporting usage on every partial chunk if counters are final-only.

## Persistence Plan

Update message serialization:

- `Message.to_dict()` includes `token_usage` when present.
- `Message.from_dict()` restores `token_usage` when present.
- Old session files without this field still load.

Update conversation serialization:

- Keep existing `total_token_usage`.
- Add a `metrics` or `api_metrics` object for aggregate performance metrics.
- Persist sums and sample counts, not only rounded averages, so restored averages remain accurate.

Example YAML shape:

```yaml
total_token_usage:
  prompt_tokens: 820
  completion_tokens: 420
  total_tokens: 1240
api_metrics:
  api_call_count: 3
  usage_call_count: 3
  speed_sample_count: 2
  output_tokens_per_second_sum: 37.2
  ttft_sample_count: 3
  ttft_ms_sum: 1560
  latency_sample_count: 3
  latency_ms_sum: 7200
```

## Status Bar Plan

`StatusBar` should accept structured data instead of only a preformatted `used/total` pair.

Potential methods:

- `update_token_usage(usage: TokenUsage | None)`.
- `update_metrics(snapshot: MetricsSnapshot)`.
- `format_token_usage(width: int)`.
- `format_performance_metrics(width: int)`.

Wide layout:

- model.
- token total and prompt/completion split.
- average speed.
- average TTFT.
- average latency.
- duration.
- working directory.
- agent status.
- mode.

Narrow layout:

- model.
- compact token total.
- one compact performance metric if available.
- agent status.

The widget should use available terminal width from Textual size information where possible. If direct width is hard to test, extract formatting into pure helper methods that receive a width.

## Testing Strategy

Use deterministic tests without real API calls.

Engine tests:

- Fake streaming client yields text chunks and final usage chunks.
- Fake clock returns fixed timestamps.
- Tests assert TTFT, latency, and `tok/s`.
- Tests assert missing usage stays unavailable.
- Tests assert aggregate averages exclude unavailable samples.

Adapter tests:

- OpenAI streaming request payload includes `stream_options.include_usage`.
- OpenAI streaming final usage is parsed.
- Custom OpenAI-compatible streaming final usage is parsed.
- Custom streaming without usage yields no token usage.
- Claude and Ollama usage normalization does not double-count.

Persistence tests:

- `Message` with `token_usage` round-trips through `to_dict()` and `from_dict()`.
- Conversation metrics round-trip through YAML serialization.
- Old session dictionaries without metrics still load.

TUI/status tests:

- Status bar formats total tokens without `/0`.
- Wide layout includes `tok/s`, `TTFT`, and latency.
- Narrow layout hides low-priority fields and remains readable.
- App consumes metrics events and updates the status bar.

Regression tests:

- Existing Agent Loop tests continue to pass.
- Existing adapter tool-call tests continue to pass.
- Existing input box tests continue to pass.

## Risks

- Some OpenAI-compatible endpoints may not support `stream_options.include_usage`.
- Providers may return cumulative usage deltas, final-only usage, or no usage.
- Tool-call streaming and usage final chunks can arrive in different provider-specific orders.
- Status bar rendering may be constrained by Textual width APIs in tests.
- Persisting only averages would make restored aggregates inaccurate, so sums and counts should be persisted.

## Rollout

Implement P0 first and run focused tests. Then add P1 timing metrics with fake-clock tests. Then add P2 persistence and narrow display.

Manual verification should use:

- one provider that returns token usage.
- one provider or fake adapter path without usage.
- one narrow terminal width.
- a restored session YAML file.
