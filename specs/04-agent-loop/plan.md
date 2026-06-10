# MewCode Agent Loop Plan

## Scope Decision

This plan implements option A: the chapter-level Agent Loop only. It includes the engine loop, event stream, stop conditions, tool batching, integration with the existing TUI, and two input interaction bug fixes on the same user-message path. It does not implement full Plan Mode or a permission/confirmation redesign.

## Current Evidence

- `src/mewcode/tui/app.py` currently drives a single-step tool flow inside `_process_with_llm`.
- `src/mewcode/engine/models/message.py` already contains `ToolCall`, `Message.tool_calls`, `Message.tool_call_id`, and `StreamChunk.tool_calls`.
- `src/mewcode/engine/models/client.py` already exposes streaming chat with optional tool definitions.
- `src/mewcode/engine/tools/registry.py` already formats tools and dispatches execution.
- `src/mewcode/engine/tools/base.py` already has `is_concurrency_safe`, `is_read_only`, and `is_destructive` metadata.
- `src/mewcode/tui/widgets/input_box.py` already owns Enter submission, input clearing, and prompt history navigation.
- Tests already cover adapters, tool calls, and individual tools.

## Architecture

Add an engine-level agent module that owns the ReAct loop. The TUI should call the agent and consume events. This moves loop control out of widgets and keeps UI rendering separate from agent decisions.

Proposed new modules:

- `src/mewcode/engine/agent_events.py`: event types and payload models.
- `src/mewcode/engine/agent.py`: agent loop, response classification, stop handling, and tool execution batches.

Updated modules:

- `src/mewcode/tui/app.py`: replace single-step LLM driver with event consumption.
- `src/mewcode/tui/widgets/input_box.py`: fix prompt clearing and Up/Down prompt history navigation if current runtime behavior does not match the widget contract.
- `src/mewcode/engine/__init__.py`: export the agent entry point if useful.
- `src/mewcode/engine/tools/registry.py`: add read-only helpers for lookup/batching if the loop needs them.
- `src/mewcode/tui/widgets/status_bar.py`: only if existing status updates cannot represent running/cancelled states cleanly.

## Data Model

Agent events should be protocol-neutral and UI-friendly. The minimum event payloads are:

- `stream_text`: text delta.
- `tool_use`: tool call id, tool name, input, and display summary.
- `tool_result`: tool call id, tool name, result content or summary, error flag, and duration.
- `turn_complete`: completed turn index.
- `loop_complete`: total turns and stop reason.
- `usage`: cumulative token counts.
- `error`: user-visible error message and optional internal detail.

Stop reasons should include:

- model completed with no tool request.
- maximum iterations reached.
- user cancelled.
- repeated invalid tool requests.
- unrecoverable error.

## Agent Loop

The loop receives:

- LLM client.
- conversation manager or an equivalent message history accessor.
- tool registry.
- system prompt builder result.
- max iteration limit.
- cancellation signal.

Per iteration:

1. Check cancellation.
2. Call `chat_stream` with system prompt, conversation messages, and formatted tools.
3. Emit `stream_text` events for text chunks.
4. Accumulate final `tool_calls` from stream chunks.
5. Persist the assistant turn with text and tool calls together.
6. Emit `usage` and `turn_complete` when data is available.
7. If no tool calls exist, emit `loop_complete` and return.
8. Execute tool calls in batches.
9. Persist tool results with matching tool call ids.
10. Continue to the next iteration.

Recoverable tool errors are sent back to the model as tool results. Unrecoverable failures emit `error` and stop the loop.

## Response Classification

Centralize response classification so future states can be added without scattering conditions through the loop.

Initial states:

- `CONTINUE`: response contains tool calls.
- `TERMINAL`: response contains no tool calls.
- `ERROR`: stream or tool execution cannot continue safely.
- `CANCELLED`: cancellation was requested.

Future states, not implemented in this scope:

- `NEED_CONFIRM`.
- `RATE_LIMITED`.
- `PLAN_REVIEW`.

## Tool Batching

The loop should partition tool calls using existing tool metadata:

- A call is concurrency-safe only when the tool exists, is enabled, and reports concurrency safety for the operation.
- Consecutive concurrency-safe calls can share one concurrent batch.
- Unsafe calls become single-call serial batches.
- Batch order must preserve the model's requested order across unsafe boundaries.

Execution rules:

- Concurrent batches run with a bounded number of tasks.
- Serial batches execute one call at a time.
- Every call produces a tool result message, even if validation fails.

## Cancellation

The TUI should keep `Ctrl+C` as app quit and add `Esc` for cancelling the active agent loop. Cancellation should stop the current request cleanly and leave the application ready for another prompt.

The agent loop should check cancellation before every model turn and before every tool batch. If cancellation happens while an awaited operation is active, the surrounding worker should convert it into a cancellation event and reset UI state.

## TUI Integration

`MewCodeApp` should:

- Create the LLM client as it does today.
- Build the tool payload format based on the active adapter as it does today.
- Start one worker per submitted user message.
- Consume agent events with `async for`.
- Update `ChatArea` on stream, tool use, and tool result events.
- Update `StatusBar` on running, usage, error, cancellation, and completion events.
- Persist conversation through the agent loop rather than duplicating message writes in the TUI.

The UI should not inspect whether the loop has more turns. It should only react to events.

## Input Prompt Bug Fixes

The input box must preserve a simple local prompt history independent of Agent Loop state.

Required behavior:

- Enter on a non-empty prompt submits exactly that prompt.
- The visible input field clears immediately after a successful non-empty submit.
- Empty prompts are not added to history.
- Up moves backward through submitted prompts.
- Down moves forward through submitted prompts.
- Down from the newest prompt restores an empty input field.
- History navigation should not submit or mutate prompts by itself.

These behaviors should be covered with widget-level tests so regressions are caught without needing a real LLM call.

## Testing Strategy

Unit tests should use fake LLM clients and fake tools. They should verify:

- terminal no-tool response.
- multi-turn tool loop.
- assistant/tool message persistence.
- max-iteration stop.
- repeated unknown-tool stop.
- cancellation stop.
- event order.
- batching behavior.
- input clearing after Enter.
- Up/Down prompt history navigation.

Integration tests should verify that TUI-facing event consumption updates chat/tool/status behavior without real network calls.

Existing adapter and tool tests must continue to pass.

## Risks

- Existing adapters may represent tool-call finish reasons differently; tests should use `StreamChunk.tool_calls` as the engine contract.
- Conversation persistence currently has a `TOOL` role; adapters must continue translating it correctly.
- Cancellation in Textual workers can leave `is_processing` stuck if cleanup is not centralized.
- Parallel tool execution must not reorder persisted results in a way that breaks model expectations.
