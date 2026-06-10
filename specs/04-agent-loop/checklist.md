# MewCode Agent Loop Checklist

## Document Approval

- [ ] User explicitly approves `spec.md` for the Agent Loop scope.
- [ ] User explicitly approves `plan.md` for the Agent Loop design.
- [ ] User explicitly approves `task.md` for the Agent Loop execution order.
- [ ] User explicitly approves this `checklist.md` before implementation begins.

## Files and Structure

- [ ] `src/mewcode/engine/agent.py` exists and exports the agent loop entry point.
- [ ] `src/mewcode/engine/agent_events.py` exists and defines event types for `stream_text`, `tool_use`, `tool_result`, `turn_complete`, `loop_complete`, `usage`, and `error`.
- [ ] `src/mewcode/tui/app.py` no longer contains the single-step tool-flow gate that ignores second-round `tool_calls`.
- [ ] `rg "single-step gate|single-step tool flow" src/mewcode` returns 0 matches after implementation.
- [ ] `src/mewcode/engine/tools/base.py` still exposes tool metadata needed for concurrency decisions.
- [ ] `tests/test_input_box.py` exists and covers prompt clearing plus Up/Down history navigation.

## Loop Behavior

- [ ] A model response with no `tool_calls` emits `loop_complete` without executing any tool.
- [ ] A model response with one `tool_call` executes that tool and starts another model turn.
- [ ] A model response with repeated `tool_calls` can run at least 3 model-tool turns for one user message.
- [ ] Assistant text and tool calls from the same model response are persisted in the same assistant message.
- [ ] Every persisted tool result keeps the original `tool_call_id`.
- [ ] Tool execution errors are returned as error tool results instead of crashing the loop.
- [ ] Unknown or disabled tools produce error tool results for the model.
- [ ] After 3 consecutive unknown or disabled tool requests, the loop emits `error` and stops.
- [ ] The loop stops after 50 iterations and emits a visible stop reason.

## Event Stream

- [ ] Streaming text chunks emit `stream_text` events before the final loop result.
- [ ] Tool call events include tool name, input, and request id.
- [ ] Tool result events include tool name, request id, error flag, summary/content, and duration in milliseconds.
- [ ] `turn_complete` is emitted once per completed LLM turn.
- [ ] `usage` events include cumulative prompt, completion, and total token counts when usage is available.
- [ ] `loop_complete` includes total turn count and a stop reason.
- [ ] `error` events include a user-visible message.

## Tool Batching

- [ ] Two concurrency-safe read/search tool calls in the same turn can execute in the same batch.
- [ ] An unsafe write/edit/bash call is isolated into a serial batch.
- [ ] For `[ReadFile, ReadFile, EditFile, ReadFile]`, batching produces concurrent read batch, serial edit batch, concurrent read batch.
- [ ] Concurrent execution respects a configured upper bound.

## TUI Integration

- [ ] Submitting one user message starts exactly one active agent worker.
- [ ] Pressing Enter on a non-empty prompt submits the prompt and clears the input field.
- [ ] Pressing Enter on an empty prompt does not add an item to prompt history.
- [ ] After submitting `first` then `second`, pressing Up once shows `second`.
- [ ] After submitting `first` then `second`, pressing Up twice shows `first`.
- [ ] After submitting `first` then `second`, pressing Up twice then Down once shows `second`.
- [ ] After submitting `first` then `second`, pressing Up once then Down once clears the input field.
- [ ] While the worker is active, the status bar shows a non-idle agent state.
- [ ] `stream_text` events append to the current assistant response.
- [ ] `tool_use` events create visible tool trace rows.
- [ ] `tool_result` events update the matching tool trace row.
- [ ] `loop_complete` returns the status bar to idle.
- [ ] Pressing `Esc` cancels the current agent loop without quitting the app.
- [ ] Pressing `Ctrl+C` still quits the app.

## Tests

- [ ] `python -m pytest tests/test_agent_loop.py -v` passes.
- [ ] `python -m pytest tests/test_agent_events.py -v` passes.
- [ ] `python -m pytest tests/test_input_box.py -v` passes.
- [ ] `python -m pytest tests/test_tui_agent_loop.py -v` passes.
- [ ] `python -m pytest tests/test_message_tool_calls.py tests/test_adapter_tool_calls.py tests/test_adapter_anthropic_tool_use.py -v` still passes.
- [ ] `python -m pytest tests/ -v` passes or any failure is documented with exact failing test names.

## End-to-End Acceptance

- [ ] Start MewCode, ask for a task that requires reading a file, editing it, and running a command; the UI shows multiple tool rounds without the user typing "continue".
- [ ] Start MewCode, ask a pure chat question; it responds without showing any tool trace.
- [ ] Start MewCode, submit two prompts, verify the input clears after each Enter, then use Up/Down to switch between the two prompts and the empty draft.
- [ ] Start MewCode, trigger a long-running request, press `Esc`, and verify the app remains open and accepts a new prompt.
