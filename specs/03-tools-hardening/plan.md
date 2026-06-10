# MewCode Tools Hardening Plan

## Architecture Overview

This chapter is a narrow hardening pass over the existing `02-tools` implementation. It adds one configuration resolution rule, several focused tests, one language-scan cleanup, and a clearer acceptance checklist. The runtime tool architecture remains unchanged.

The work is split into five small components:

- **Configuration resolution**: resolve a model API key from an environment variable first, then fall back to the existing plaintext config key.
- **Documentation examples**: document the environment-first behavior without removing plaintext-key compatibility and without publishing a real secret in examples.
- **Language-strategy cleanup**: remove Chinese characters from tool implementation files while preserving English model-visible strings.
- **Automated acceptance tests**: add tests for TUI tool traces, single-step tool flow, and payload/language policy.
- **Checklist reorganization**: rewrite the hardening checklist so automated, manual TUI, and real API checks are separated.

No adapter protocol behavior, tool execution behavior, session format, or TUI layout is redesigned.

## Core Data Structures

### Model Configuration

The existing per-model config dictionary remains the public shape used by the app. This chapter adds one optional config field:

| Field | Type | Purpose |
|------|------|---------|
| `api_key` | string | Existing plaintext key fallback. Remains supported. |
| `api_key_env` | string | Optional environment variable name. If set and the environment variable has a non-empty value, that value overrides `api_key`. |

Resolved model config is still a dictionary. Callers receive the same keys they already use, with `api_key` replaced by the environment value when applicable.

### Fake Stream Client

TUI flow tests need a lightweight model double that behaves like the existing LLM client interface.

| Attribute / Method | Purpose |
|------|---------|
| `calls` | Counts how many times the app invoked the model stream. |
| `chat_stream(messages, tools=None, **kwargs)` | Yields predetermined `StreamChunk` objects for first and second model calls. |
| `close()` | No-op async method so app teardown stays compatible. |

Each scenario can provide its own fake client class or a small configurable helper.

### Captured Payload

Payload tests use the existing fake stream pattern from adapter tests. The test stores request fields in an in-memory dictionary:

| Field | Purpose |
|------|---------|
| `payload` | Captured JSON payload passed to the fake stream call. |
| `method` | Captured HTTP method. |
| `url` | Captured request URL. |

The payload is inspected for system message text, tool descriptions, and absence of tool metadata.

## Module Design

### Configuration Module

**Responsibilities:**
- Load YAML config exactly as before.
- Resolve model-specific config exactly as before, plus environment override support.
- Keep plaintext-key fallback behavior unchanged.

**Interface changes:**
- Existing model config lookup will return a copy rather than the original nested dictionary.
- If the resolved model config names an environment variable and that variable is non-empty, the returned config's API key value is replaced by that environment value.
- If the environment variable is missing or empty, the returned config keeps the plaintext key value.

**Spec coverage:** F1, F2, F3, N1, N2, AC1, AC2, AC3.

### TUI App Integration

**Responsibilities:**
- Continue using model config lookup as the only source for adapter creation parameters.
- Benefit from the environment-first key resolution without app-level branching.

**Interface changes:**
- No new TUI app public API.
- Existing client creation path continues to request the model config and pass `api_key`, `base_url`, provider, and API format into the adapter factory.

**Spec coverage:** F1, F2, N3.

### Tool Language Cleanup

**Responsibilities:**
- Remove Chinese characters from files under the tool implementation directory.
- Keep tool names, descriptions, schemas, system prompt, and tool result content English.

**Implementation approach:**
- Replace the non-runtime Chinese documentation reference in the tool system prompt module with English wording.
- Avoid changing runtime prompt content unless required by tests.

**Spec coverage:** F4, AC4, AC5.

### TUI Tool Trace Tests

**Responsibilities:**
- Prove the pending, success, and error trace states are produced by the chat area widget.
- Avoid real terminal interaction.

**Implementation approach:**
- Use Textual test mode to mount the app or widget.
- Call the trace methods directly or through the app flow.
- Inspect the resulting widget text/renderable state with the supported Textual API for this project version.

**Spec coverage:** F5, AC6.

### Single-Step Flow Tests

**Responsibilities:**
- Prove the app's single-step tool loop works for success, failure, shell command, second-response suppression, and pure chat.
- Avoid live LLM and network access.

**Implementation approach:**
- Use Textual test mode with fake LLM clients.
- Inject the fake client before sending a message.
- Assert the conversation roles and tool result fields after the worker finishes.

Scenarios:
- ReadFile success: user -> assistant with tool call -> tool -> assistant final.
- ReadFile missing file: tool result has error flag and final reply still appears.
- Bash command: tool result contains command output and final reply appears.
- Second response emits a new tool call: no second tool result is added.
- Pure chat: only user and assistant messages are added.

**Spec coverage:** F6, AC7, AC8, AC9, AC10, AC11.

### Payload and Language Policy Tests

**Responsibilities:**
- Prove request payload construction includes the tool system prompt and enabled tool descriptions.
- Prove model-visible system prompt and tool descriptors contain no Chinese characters.
- Prove tool execution metadata is not added to model-visible messages.

**Implementation approach:**
- Reuse the fake adapter stream pattern already present in adapter tests.
- Build representative messages that include assistant tool calls and tool results.
- Capture the outgoing payload and inspect only model-visible fields.
- Build a registry and system prompt in-process, then scan strings with a Unicode CJK matcher.

**Spec coverage:** F7, N2, AC5, AC12.

### Checklist and Changelog

**Responsibilities:**
- Create a hardening checklist that can be used as a reliable test report template.
- Record completed changes and validation commands after implementation.

**Checklist sections:**
- Automated checks: unit tests, fake TUI flow tests, payload tests, static scans.
- Manual TUI checks: real terminal observation of trace rendering and usability.
- Real API checks: optional live model validation.

**Spec coverage:** F8, F9, N6, AC13, AC15.

## Module Interaction

### Runtime Config Resolution

```text
MewCodeApp
  -> load_config()
  -> get model config
       -> read per-model config
       -> if api_key_env names a non-empty environment variable:
              use environment value as api_key
          else:
              keep plaintext api_key
  -> AdapterFactory.create_client(api_key=resolved_api_key, ...)
```

The adapter factory and individual adapters do not need to know whether the key came from the environment or plaintext config.

### Fake TUI Flow Test

```text
Test
  -> create MewCodeApp in Textual test mode
  -> inject fake LLM client
  -> submit user message
  -> app first stream receives tool call
  -> app executes local tool
  -> app appends tool result message
  -> app second stream receives final text
  -> test asserts conversation roles, flags, and model call count
```

### Payload Language Test

```text
Test
  -> build ToolContext and ToolRegistry
  -> build system message
  -> call adapter.chat_stream with fake stream
  -> capture payload
  -> assert system message and tool descriptions are present
  -> assert CJK scan over model-visible strings is false
  -> assert tool metadata is absent from messages
```

## File Organization

```text
specs/03-tools-hardening/
├── spec.md       -- approved requirements
├── plan.md       -- this document
├── task.md       -- next phase
└── checklist.md  -- final acceptance checklist

src/mewcode/
├── config.py
│   -- add environment-first model key resolution while preserving plaintext fallback
├── engine/tools/system_prompt.py
│   -- remove non-English doc/comment text from tool implementation directory
└── tui/
    └── app.py
        -- no behavior change expected; tests exercise existing flow

tests/
├── test_config_env.py
│   -- environment key precedence and plaintext fallback
├── test_tui_tool_flow.py
│   -- fake single-step TUI flow scenarios
├── test_tui_tool_trace.py
│   -- pending/success/error trace rendering
└── test_payload_language.py
    -- payload construction and model-visible language policy

README.md
MANUAL.md
config.yaml
CHANGELOG.md
```

`config.yaml` may add an optional environment-variable field for the existing configured model while preserving the existing plaintext key. Documentation examples must use placeholders and must not expose real secrets.

## Technical Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Environment override location | Config lookup layer | Keeps adapter and TUI code simple; every caller gets resolved config consistently. |
| Plaintext support | Preserve as fallback | Matches user requirement and avoids breaking current local setup. |
| Config shape | Add optional environment-variable-name field | Explicit, readable, and compatible with YAML config. |
| Empty environment values | Treat as absent | Avoids accidentally replacing a working plaintext key with an empty value. |
| Secret handling in docs/tests | Use placeholders only | Prevents accidental credential disclosure while documenting behavior. |
| TUI flow tests | Textual test mode with fake clients | Exercises app-level behavior without network or real terminal interaction. |
| Payload tests | Fake adapter stream capture | Reuses established testing pattern and avoids live API calls. |
| Language scan | Separate file-level scan from model-visible scan | The checklist needs both: strict tool-file hygiene and behavior-level language assurance. |
| Checklist structure | Split automated/manual/real API sections | Makes future test reports precise; skipped manual checks are not confused with failed automated checks. |
| Existing `02-tools` docs | Keep unchanged | They document the original implementation chapter; hardening gets its own chapter. |
