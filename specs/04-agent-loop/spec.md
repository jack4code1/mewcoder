# MewCode Agent Loop Spec

## Background

MewCode already has model adapters, conversation history, a TUI, and six core tools for reading, writing, searching, editing, and running commands. The current tool flow can complete only one tool round: the model asks for tools, MewCode executes them, then the model gives a final answer. For a coding assistant this is not enough, because real tasks usually require repeated observation and adjustment.

This feature turns the existing one-step tool flow into a ReAct-style Agent Loop: the model can think, act through tools, observe results, and continue until it decides the task is complete or the loop is stopped safely.

This feature also includes two existing TUI input regressions that affect the same interaction path: submitted prompt text must clear after Enter, and users must be able to navigate submitted prompts with the Up and Down arrow keys.

## Target Users

- Developers using MewCode as a terminal AI coding assistant.
- Users who expect MewCode to complete multi-step coding tasks without being prompted after every tool call.
- Future maintainers who need a clear engine/UI boundary for testing and extending agent behavior.

## Capability List

- The agent can run multiple model-tool turns for one user request.
- The agent can stream model text to the UI while the loop is running.
- The agent can emit structured events for tool calls, tool results, token usage, turn completion, loop completion, and errors.
- The agent can stop naturally when the model no longer requests tools.
- The agent can stop safely when it hits an iteration limit.
- The agent can stop cleanly when the user cancels the current request.
- The agent can detect repeated abnormal tool requests and stop instead of looping indefinitely.
- The agent can execute concurrency-safe tool calls in the same model turn in parallel batches.
- The agent can execute side-effecting or unsafe tool calls serially.
- The UI can consume agent events without knowing the internal loop implementation.
- Existing single-message chat behavior remains available when the model does not request tools.
- The input field is cleared after a non-empty prompt is submitted with Enter.
- The input field supports fast prompt history navigation with Up and Down.

## Non-Functional Requirements

- Correctness is more important than speed.
- The loop must not run forever.
- Tool result messages must preserve the relationship with the original tool request.
- Streaming UI updates must remain responsive during long-running tasks.
- Input submission and history navigation must remain responsive while the app is idle.
- Agent engine code must be testable without launching the TUI.
- Existing adapters, tools, and conversation models should be reused where practical.
- Error results from tools should be returned to the model when recoverable.
- System-level failures should surface as agent errors rather than being hidden.
- The design should allow later extension for confirmation gates, rate limiting, and richer planning modes.

## Design Skeleton

The feature adds an engine-level Agent Loop between the TUI and the existing LLM/tool subsystems.

The loop receives a user message plus the current conversation state. It calls the active model with the enabled tool definitions. If the model streams plain text only, the loop emits text events and completes. If the model requests tools, the loop records the assistant turn, executes the requested tools, records matching tool results, emits tool events, then starts another model turn.

The loop exposes its progress as an asynchronous event stream. The TUI consumes that stream to update the chat area, tool trace, status bar, and completion state. The agent engine does not directly manipulate widgets.

The input widget remains responsible for prompt submission and local prompt history. Submitting a prompt clears the visible input field immediately after the submission is accepted. Up and Down navigate only through submitted non-empty prompts and restore an empty field after the newest history entry.

Stop behavior is part of the product requirement, not an implementation detail. A request must stop when the model finishes, when the loop exceeds its configured safety limit, when the user cancels, or when repeated invalid tool requests show the loop is no longer making useful progress.

Tool execution follows the existing tool metadata. Read-only and concurrency-safe calls may be grouped and run together. Unsafe calls remain serial to avoid accidental races or overlapping writes.

## Out of Scope

- Full permission and approval system redesign.
- Full Plan Mode implementation.
- Destructive-operation confirmation UX.
- New tools beyond the existing tool set.
- New LLM providers or adapter rewrites unrelated to loop support.
- Long-term memory, project indexing, or persistent background agents.
- Web UI, JSON CLI mode, or non-TUI frontends.
- Automatic git commits or deployment actions.
