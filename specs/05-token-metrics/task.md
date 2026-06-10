# MewCode Token Metrics Tasks

## Task 1: Define Metrics Data Models

**Impact files:** `src/mewcode/engine/models/metrics.py`, `src/mewcode/engine/models/__init__.py`, `tests/test_metrics_models.py`

**Depends on:** none

**Reference:** `spec.md` Metric Definitions; `plan.md` Data Model section

**Work:**

- Add a per-call API metrics dataclass.
- Add a session aggregate metrics dataclass.
- Represent unavailable values with `None` and sample counts.
- Add average properties for `tok/s`, TTFT, and latency.
- Add helpers for adding one completed call into the aggregate.

**Verification:**

- `python -m pytest tests/test_metrics_models.py -v -p no:cacheprovider`

## Task 2: Serialize Token Usage and Metrics

**Impact files:** `src/mewcode/engine/models/message.py`, `src/mewcode/engine/conversation.py`, `tests/test_message_token_usage.py`, `tests/test_conversation_metrics.py`

**Depends on:** Task 1

**Reference:** `src/mewcode/engine/models/message.py` `Message.to_dict` and `Message.from_dict`; `src/mewcode/engine/conversation.py` `Conversation.to_dict` and `Conversation.from_dict`; `plan.md` Persistence Plan

**Work:**

- Serialize `Message.token_usage` when present.
- Deserialize `Message.token_usage` when present.
- Persist aggregate API metrics in conversation dictionaries and YAML.
- Restore aggregate API metrics from saved sessions.
- Keep old session dictionaries without metrics loadable.

**Verification:**

- Message token usage round-trips through dict serialization.
- Conversation metrics round-trip through dict and YAML serialization.
- Old fixture data without `api_metrics` still loads.

## Task 3: Extend Agent Events for Metrics

**Impact files:** `src/mewcode/engine/agent_events.py`, `tests/test_agent_events.py`

**Depends on:** Task 1

**Reference:** `plan.md` Agent Event Design; existing `AgentEvent.usage`

**Work:**

- Add a metrics payload or a dedicated metrics event type.
- Keep existing usage event behavior compatible where practical.
- Ensure event payloads can carry cumulative tokens and aggregate averages.
- Add tests for metrics event construction and fields.

**Verification:**

- `python -m pytest tests/test_agent_events.py -v -p no:cacheprovider`

## Task 4: Instrument Agent Loop Timing

**Impact files:** `src/mewcode/engine/agent.py`, `tests/test_agent_loop_metrics.py`, `tests/test_agent_loop.py`

**Depends on:** Tasks 1 and 3

**Reference:** `src/mewcode/engine/agent.py` `run_agent_loop`; `plan.md` Timing Strategy

**Work:**

- Record request start before each `chat_stream` call.
- Record first non-empty streamed content time for TTFT.
- Record request end after stream completion.
- Calculate per-call latency, TTFT, and `tok/s`.
- Update the metrics aggregate.
- Emit metrics snapshots to the TUI.
- Do not block existing stream text events.

**Verification:**

- Fake stream with first token at 0.5s reports `TTFT = 500ms`.
- Fake stream completing at 2.5s reports `latency = 2500ms`.
- Fake stream with 20 completion tokens over a 2.0s output window reports `10.0 tok/s`.

## Task 5: Normalize Adapter Usage

**Impact files:** `src/mewcode/engine/adapters/openai_adapter.py`, `src/mewcode/engine/adapters/custom_adapter.py`, `src/mewcode/engine/adapters/claude_adapter.py`, `src/mewcode/engine/adapters/ollama_adapter.py`, adapter tests under `tests/`

**Depends on:** Task 1

**Reference:** `plan.md` Adapter Plan; `rg -n "token_usage|usage" src/mewcode/engine/adapters`

**Work:**

- Request OpenAI-compatible streaming usage with `stream_options.include_usage` when supported.
- Parse OpenAI-compatible final streaming usage chunks.
- Stop emitting placeholder `TokenUsage()` for missing usage in custom streaming.
- Confirm Claude streaming usage is not double-counted.
- Confirm Ollama final usage counters are mapped once.
- Keep tool-call streaming behavior unchanged.

**Verification:**

- OpenAI streaming request payload contains `stream_options: {"include_usage": true}`.
- Streaming usage object `{prompt_tokens: 10, completion_tokens: 20, total_tokens: 30}` yields `TokenUsage(10, 20, 30)`.
- Missing usage yields no usage event and UI displays `N/A`, not `0`.

## Task 6: Update Status Bar Formatting

**Impact files:** `src/mewcode/tui/widgets/status_bar.py`, `tests/test_status_bar_metrics.py`

**Depends on:** Tasks 1 and 3

**Reference:** `spec.md` Display Requirements; current `StatusBar.update_token_usage`

**Work:**

- Replace `used/total` formatting with real token display.
- Add display fields for average `tok/s`, TTFT, and latency.
- Format unavailable metrics as `N/A`.
- Add compact number formatting for large token counts.
- Add width-aware formatting helpers for wide and narrow status bars.

**Verification:**

- Status bar no longer formats real total token usage as `123/0`.
- Wide format includes `tok/s`, `TTFT`, and `Lat`.
- Narrow format hides full working directory and still shows model, tokens, one performance metric, and agent status.

## Task 7: Wire Metrics into the TUI

**Impact files:** `src/mewcode/tui/app.py`, `tests/test_tui_agent_loop.py`, `tests/test_tui_metrics.py`

**Depends on:** Tasks 3, 4, and 6

**Reference:** `src/mewcode/tui/app.py` handling of `AgentEventType.USAGE`; `plan.md` Status Bar Plan

**Work:**

- Consume usage and metrics events from the Agent Loop.
- Update status bar token display with real prompt, completion, and total values.
- Update status bar speed, TTFT, and latency averages from metrics snapshots.
- Preserve existing running, idle, error, and loop completion status updates.

**Verification:**

- Fake Agent Loop event sequence updates status bar to show total tokens and averages.
- Existing multi-turn TUI Agent Loop test still passes.

## Task 8: Add Metrics Persistence Tests and Session Fixtures

**Impact files:** `tests/test_conversation_metrics.py`, `tests/fixtures/` if needed

**Depends on:** Tasks 1 and 2

**Reference:** `spec.md` Persistence Requirements; `plan.md` Persistence Plan

**Work:**

- Add tests for saving nonzero metrics into session YAML.
- Add tests for reloading metrics from session YAML.
- Add tests for loading old sessions without metrics.
- Add tests that message-level token usage survives persistence.

**Verification:**

- Saved YAML contains `total_token_usage` and `api_metrics`.
- Reloaded conversation has the same token totals and average metrics.

## Task 9: Update User Documentation

**Impact files:** `README.md`, `MANUAL.md`, `CHANGELOG.md`

**Depends on:** Tasks 6 and 7

**Reference:** user-visible behavior in `spec.md`; project changelog convention

**Work:**

- Document status bar token and API metrics.
- Document unavailable metrics display as `N/A`.
- Add changelog entry for token metrics, usage parsing, persistence, and narrow status bar behavior.

**Verification:**

- `rg "tok/s|TTFT|latency|token" README.md MANUAL.md CHANGELOG.md` returns relevant entries.

## Task 10: Connect Main Flow and Run End-to-End Validation

**Impact files:** `src/mewcode/tui/app.py`, `src/mewcode/engine/agent.py`, tests listed in `checklist.md`

**Depends on:** Tasks 1 through 9

**Reference:** `checklist.md` Tests and End-to-End Acceptance sections

**Work:**

- Ensure the default `mewcode` TUI path uses the new metrics flow.
- Run focused unit tests for metrics, adapters, persistence, and status bar formatting.
- Run existing Agent Loop and TUI tests.
- Run the full test suite.
- Manually launch MewCode and verify visible metrics.

**Verification:**

- `python -m pytest tests -v -p no:cacheprovider`
- Manual verification results are recorded in the final implementation summary.
