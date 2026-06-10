# MewCode Agent Loop Tasks

## Task 1: Define Agent Event Models

**Impact files:** `src/mewcode/engine/agent_events.py`, `tests/test_agent_events.py`

**Depends on:** none

**Reference:** `spec.md` capability list; `plan.md` Data Model section; `src/mewcode/engine/models/message.py`

**Work:**

- Define event types for stream text, tool use, tool result, turn complete, loop complete, usage, and error.
- Define stop reasons used by loop completion.
- Add serialization or simple field assertions if useful for tests.

**Verification:**

- `python -m pytest tests/test_agent_events.py -v`

## Task 2: Build Agent Loop Skeleton

**Impact files:** `src/mewcode/engine/agent.py`, `src/mewcode/engine/__init__.py`, `tests/test_agent_loop.py`

**Depends on:** Task 1

**Reference:** `plan.md` Agent Loop and Response Classification sections; `src/mewcode/engine/models/client.py`

**Work:**

- Add an async event-stream entry point for one user request.
- Call the LLM client with current messages and tools.
- Stream text chunks as events.
- Accumulate tool calls from stream chunks.
- Classify responses into continue or terminal.

**Verification:**

- Fake LLM test for no-tool terminal response passes.

## Task 3: Persist Assistant and Tool Messages Correctly

**Impact files:** `src/mewcode/engine/agent.py`, `tests/test_agent_loop.py`

**Depends on:** Task 2

**Reference:** `src/mewcode/engine/models/message.py`; chapter note that assistant text and tool use must not be split

**Work:**

- Persist assistant text and tool calls in the same assistant message.
- Persist tool results with matching tool call ids.
- Preserve recoverable tool errors as model-visible tool results.

**Verification:**

- Tests assert assistant message includes both content and tool calls.
- Tests assert every tool result has the original id.

## Task 4: Add Stop Conditions

**Impact files:** `src/mewcode/engine/agent.py`, `tests/test_agent_loop.py`

**Depends on:** Task 3

**Reference:** `spec.md` stop behavior; `plan.md` Stop reasons

**Work:**

- Stop when the model emits no tool calls.
- Stop after the max iteration limit.
- Stop on cancellation.
- Stop after repeated unknown or disabled tool requests.
- Emit loop completion or error events with clear stop reasons.

**Verification:**

- Tests cover natural completion, max iteration, cancellation, and repeated invalid tools.

## Task 5: Implement Tool Batching

**Impact files:** `src/mewcode/engine/agent.py`, `src/mewcode/engine/tools/registry.py`, `tests/test_agent_loop.py`

**Depends on:** Task 3

**Reference:** `plan.md` Tool Batching section; `src/mewcode/engine/tools/base.py`

**Work:**

- Partition tool calls into concurrent and serial batches.
- Run concurrency-safe batches with a bounded limit.
- Run unsafe calls serially.
- Keep result association by tool call id.

**Verification:**

- Tests cover `[ReadFile, ReadFile, EditFile, ReadFile]` batch partitioning.
- Tests cover concurrent-safe calls completing successfully.

## Task 6: Fix Input Prompt UX Regressions

**Impact files:** `src/mewcode/tui/widgets/input_box.py`, `tests/test_input_box.py`

**Depends on:** none

**Reference:** `src/mewcode/tui/widgets/input_box.py`; `plan.md` Input Prompt Bug Fixes section

**Work:**

- Ensure Enter submits a non-empty prompt and clears the visible input field.
- Ensure empty prompts are not added to prompt history.
- Ensure Up navigates to older submitted prompts.
- Ensure Down navigates to newer submitted prompts and returns to an empty field after the newest item.
- Add widget-level tests for prompt clearing and history navigation.

**Verification:**

- `python -m pytest tests/test_input_box.py -v`

## Task 7: Replace TUI Single-Step Driver with Event Consumption

**Impact files:** `src/mewcode/tui/app.py`, `tests/test_tui_agent_loop.py`

**Depends on:** Tasks 1-5

**Reference:** `src/mewcode/tui/app.py` `_process_with_llm`; `plan.md` TUI Integration section

**Work:**

- Replace the current single-step flow with an agent event consumer.
- Render stream text, tool use, and tool results from events.
- Update status bar for running, usage, errors, and completion.
- Keep existing pure-chat behavior.

**Verification:**

- TUI tests verify multi-turn flow no longer ignores second-round tool calls.

## Task 8: Add User Cancellation

**Impact files:** `src/mewcode/tui/app.py`, `src/mewcode/engine/agent.py`, `tests/test_tui_agent_loop.py`

**Depends on:** Task 7

**Reference:** `plan.md` Cancellation section; existing `BINDINGS` in `src/mewcode/tui/app.py`

**Work:**

- Bind `Esc` to cancel the active loop.
- Preserve `Ctrl+C` for application quit.
- Ensure cleanup resets `is_processing` and status bar state.

**Verification:**

- Test or manual check shows cancellation leaves the app open and ready for new input.

## Task 9: Connect Main Flow

**Impact files:** `src/mewcode/tui/app.py`, `src/mewcode/engine/__init__.py`, `README.md`, `MANUAL.md`, `CHANGELOG.md`

**Depends on:** Tasks 6-8

**Reference:** `CLAUDE.md` requires changelog update after development and acceptance

**Work:**

- Ensure the default TUI path uses the Agent Loop for submitted messages.
- Update user-facing docs only where behavior changes.
- Update changelog with implementation notes.

**Verification:**

- `rg "single-step gate|single-step tool flow" src/mewcode` returns 0 matches.

## Task 10: End-to-End Validation

**Impact files:** `tests/test_agent_loop.py`, `tests/test_tui_agent_loop.py`, `tests/test_input_box.py`, test fixtures as needed

**Depends on:** Task 9

**Reference:** `checklist.md` End-to-End Acceptance section

**Work:**

- Run focused agent and TUI tests.
- Run input box regression tests.
- Run existing tool-call adapter tests.
- Run the full test suite.
- Manually validate a pure chat request, a multi-tool request, and cancellation.

**Verification:**

- `python -m pytest tests/ -v`
- Manual results recorded in the final implementation summary.
