# MewCode Token Metrics Spec

## Background

MewCode already streams model output, executes tools through the Agent Loop, and emits token usage events when adapters provide usage data. The current TUI status bar does not show a useful token summary yet:

- `src/mewcode/tui/app.py` sends `event.usage.total_tokens` as the first value and always sends `0` as the second value.
- `src/mewcode/tui/widgets/status_bar.py` formats token usage as `used/total`, so the UI can show values like `123/0`.
- `src/mewcode/engine/models/message.py` has `Message.token_usage`, but `Message.to_dict()` and `Message.from_dict()` do not persist that field.
- The Agent Loop has no timing metrics for API calls, first token latency, total latency, or output speed.
- Some adapters parse usage only when the provider returns it, and OpenAI-compatible streaming requests do not yet explicitly ask for final usage data where the protocol supports it.

This feature makes token and API performance metrics visible, accurate, and persisted enough for users to evaluate model behavior during a session.

## Target Users

- Developers using MewCode interactively who want to see whether a request is consuming tokens.
- Users comparing different model providers or custom endpoints.
- Maintainers debugging adapter behavior and streaming performance.
- Future work that may add cost estimation, rate limits, or benchmark reporting.

## Priority Levels

### P0

- The UI displays real token usage instead of `0` placeholders.
- Adapters correctly capture usage data when the provider returns it.
- Missing provider usage is represented as unavailable, not as a fake zero.

### P1

- The UI displays session average API output speed in `tok/s`.
- The UI displays average first-token latency, also called TTFT.
- The UI displays average total API latency.

### P2

- Metrics persist into session YAML and can be restored.
- The status bar remains readable on narrow terminal widths.

## Capability List

- MewCode can distinguish known-zero token usage from unavailable token usage.
- MewCode can display cumulative prompt, completion, and total tokens in the status bar or a status-friendly compact form.
- MewCode can emit structured metric events from the Agent Loop.
- MewCode can calculate per-call total latency from model request start to stream completion.
- MewCode can calculate first-token latency from model request start to the first non-empty streamed text delta.
- MewCode can calculate output speed from completion tokens divided by streaming duration after the first output when enough data exists.
- MewCode can aggregate metrics across API calls in the active session.
- MewCode can show averages for `tok/s`, TTFT, and latency.
- MewCode can request OpenAI-compatible streaming usage data when the provider supports the option.
- MewCode can normalize usage from OpenAI, Claude, Ollama, and custom adapters into the existing `TokenUsage` model.
- MewCode can persist aggregate token and performance metrics to session YAML.
- MewCode can reload persisted aggregate metrics when a session is restored.
- MewCode can keep the status bar readable in both wide and narrow terminal layouts.
- Tests can validate metrics without making real network API calls.

## Non-Functional Requirements

- Accuracy matters more than having a value for every provider.
- Do not invent token counts, speeds, or latency values.
- Do not display unavailable usage as `0` unless the provider explicitly returned a true zero.
- Timing calculations must use a monotonic clock so system clock changes do not corrupt latency values.
- Metrics collection must not block streaming output.
- Metrics collection must work in tests with deterministic fake clocks or injected timestamps.
- Existing Agent Loop behavior, tool execution, and input history behavior must not regress.
- Session YAML must remain backward-compatible with old files that do not contain metrics.
- User-facing status text should remain compact enough for terminal use.
- Provider-specific quirks should be contained in adapters or normalization helpers, not scattered through the TUI.

## Design Skeleton

The feature adds a metrics layer around existing streaming model calls.

The Agent Loop is the right place to time model calls because it already owns the request lifecycle. For each model turn, it records the start time before `chat_stream`, records the first non-empty text chunk time, accumulates token usage chunks, and records the end time when streaming finishes or fails. From those points it creates a per-call metrics object.

The Agent Loop then updates a session-level metrics aggregate and emits an event that the TUI can consume. Token usage can continue to use the existing `usage` event or can be carried inside a richer metrics event, but the UI must receive enough information to render cumulative tokens and averages without recalculating provider-specific details.

Adapters remain responsible for provider wire formats. They parse usage returned by the API and map it into the protocol-neutral `TokenUsage` class. OpenAI-compatible streaming adapters should request final usage data using the provider-supported streaming option. If a provider or endpoint does not provide usage, the adapter should yield no usage instead of a zero-valued usage object that looks authoritative.

Conversation persistence stores aggregate token and API metrics. Message-level token usage should also serialize when present so old and restored sessions can explain where totals came from.

The status bar displays a concise summary. A wide terminal can show tokens, speed, TTFT, and latency. A narrow terminal should prefer model, token total, compact metrics, and agent state, while hiding lower-priority fields such as full working directory.

## Metric Definitions

- `prompt_tokens`: input tokens reported by the provider for a model call.
- `completion_tokens`: output tokens reported by the provider for a model call.
- `total_tokens`: provider total when available, otherwise prompt plus completion only when both are known.
- `TTFT`: time from model request start to the first non-empty streamed text delta.
- `latency`: time from model request start to stream completion.
- `tok/s`: completion tokens divided by output duration when completion tokens and timing are available.
- `output_duration`: time from first non-empty streamed text delta to stream completion.
- `average TTFT`: arithmetic mean of calls that have TTFT.
- `average latency`: arithmetic mean of completed calls that have latency.
- `average tok/s`: arithmetic mean of calls that have a valid per-call output speed.

## Display Requirements

Wide status bar should expose these concepts:

- model name.
- total token usage with at least total tokens visible.
- prompt and completion token split when space allows.
- average output speed in `tok/s` when available.
- average TTFT when available.
- average latency when available.
- agent state.
- mode.

Unavailable values should display as `N/A`, not `0`.

Example wide display shape:

```text
[gpt-4o-mini] [Tok: 1,240 P:820 C:420] [Avg: 18.6 tok/s TTFT: 520ms Lat: 2.4s] [00:08:31] [E:\agent_class\project] [Idle] [Chat]
```

Example narrow display shape:

```text
[gpt-4o-mini] [Tok: 1.2k] [18.6 tok/s] [Idle]
```

The exact punctuation can change during implementation, but the information must be observable and covered by tests.

## Persistence Requirements

Session YAML should preserve:

- aggregate token usage.
- aggregate API call count.
- aggregate or reconstructable average `tok/s`.
- aggregate or reconstructable average TTFT.
- aggregate or reconstructable average latency.
- message-level token usage when present.

Backward compatibility:

- Old session files without metrics still load.
- Missing metrics load as unavailable or zero-count aggregates.
- Existing `total_token_usage` remains readable.

## Out of Scope

- Price or cost accounting.
- Provider billing dashboards.
- Long-term cross-session analytics.
- External observability integrations.
- A model benchmarking suite.
- A full TUI redesign.
- Token estimation when provider usage is unavailable.
- Per-tool token accounting.
- Rate-limit prediction.
- Changing model selection behavior.
