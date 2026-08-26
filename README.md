# MewCode

MewCode is a terminal AI coding assistant built with Python and Textual. It
supports OpenAI-compatible endpoints, Claude, Ollama, MCP tools, project
memory, execution planning, and approval-gated file and shell operations.

## Requirements

- Python 3.10 or newer
- An API key for the model provider you choose, unless using a local Ollama
  model

## Install

```bash
python -m pip install .
```

For development dependencies:

```bash
python -m pip install -e ".[dev]"
```

## Configure and run

1. Copy or edit `config.yaml` to select a model and provider. Put local API
   keys or overrides in the ignored `config.local.yaml` file.
2. Set the API key environment variable configured for the selected model.
3. Start the terminal application:

```bash
mewcode
```

You can also select a configured model or provider at launch:

```bash
mewcode --model glm-5.2 --provider openai
```

## Safety

State-changing tools, including shell commands and file edits, require user
approval when `security.enabled` is enabled. Project-level approvals are
stored in `.mewcode/permissions.json`, which is ignored by Git.

## Development

Run the test suite with:

```bash
python -m pytest -q
```

The project source files are UTF-8 and include Chinese routing keywords so
Chinese coding requests are classified without relying on an LLM router.

## Multi-agent execution

MewCode uses a single-process, role-based multi-agent runtime. It reuses the
configured LLM client rather than starting one model process per role.

- `AgentRuntime` gives each role a private conversation, tool allow-list,
  step/token/time budgets, cancellation handling, and structured result.
- `AgentTask` and `TaskGraph` validate roles, dependencies, state
  transitions, and the intersection of registered tools, role policy, and
  task-requested tools.
- `InMemoryMessageBus` provides validated, deduplicated task messages and
  per-agent inboxes. It is an in-process interface designed to be replaceable
  by external transport later.
- `SharedTaskBoard` stores task summaries, artifact references, review/test
  decisions, and an execution trace. `view_for()` exposes only a task's own
  inputs, dependency summaries, and addressed messages.
- `StructuredTaskScheduler` may run non-conflicting read-only tasks together;
  write-capable tasks remain serial in the shared workspace. Existing Git
  worktree execution is retained for isolated tasks.
- `WorktreeTaskScheduler` is available for structured write tasks: it creates
  one clean Git worktree per non-conflicting task, stores the resulting diff as
  a board artifact, and requires explicit per-task application to the clean
  main worktree. It refuses unsafe application when the main worktree is
  dirty.

The interactive team command remains deliberately serial and follows
research → implementation → review → repair (bounded) → test. Review verdicts
accept structured `{ "verdict": "PASS|FIX" }` payloads while remaining
compatible with the legacy `VERDICT: PASS/FIX` convention.
