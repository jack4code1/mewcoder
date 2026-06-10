# MewCode Tools Hardening Spec

> Chapter: 03-tools-hardening
> Previous chapter: `specs/02-tools`
> Scope: validation fixes, configuration hardening, and automated acceptance coverage for the single-step tools system.

## Background

The single-step tools system is implemented and the current automated suite passes, but one checklist run exposed several gaps between the intended acceptance process and what can be reliably verified:

- The runtime configuration currently supports a plaintext API key in the project config. This should remain supported for local compatibility, but environment variables should be able to override it so credentials do not need to live in the repository.
- The tool implementation directory still contains a Chinese text hit in non-runtime documentation text, causing the language-strategy scan to fail even though model-visible tool strings are English.
- The checklist mixes automated checks, manual TUI checks, and real API checks in one list, making the result hard to classify.
- The TUI single-step tool flow was verified manually with temporary scripts, but those scenarios are not yet permanent tests.
- The request payload language policy is partly covered by adapter tests, but there is no focused acceptance check that proves model-visible strings stay English.

This chapter tightens the existing tools system without changing the product boundary of chapter 02. It does not add multi-step agent loops, permissions, confirmation UI, or new tools.

## Goals

- Preserve existing plaintext API-key configuration as a fallback while allowing environment variables to override it.
- Make the language-strategy scan for tool implementation files pass without weakening the English-only requirement for model-visible tool text.
- Add automated coverage for TUI tool-call traces and the single-step tool flow using mock model clients.
- Add automated coverage for request payload construction and model-visible language policy.
- Restructure the tools checklist so automated, manual TUI, and real API checks are clearly separated.
- Keep all existing tool behavior and pure chat behavior compatible with chapter 02.

## Functional Requirements

- F1: The model configuration must support an environment-based API-key override, and that override must take precedence over the plaintext key when both are present.
- F2: Plaintext API-key configuration must continue to work when no matching environment value is available.
- F3: The project configuration example and user-facing documentation must describe the environment-first key behavior without removing the existing plaintext option.
- F4: Tool implementation files must pass a file-level scan for Chinese characters, while all model-visible tool strings remain English.
- F5: Automated tests must cover the TUI tool-call trace states for pending, success, and error display.
- F6: Automated tests must cover the single-step tool flow for a successful read, a failed read, a shell command, second-response tool-call suppression, and pure-chat fallback.
- F7: Automated tests must verify that request payload construction includes the tool system prompt and tool descriptions in English.
- F8: The tools checklist must be reorganized into automated checks, manual TUI checks, and real API checks, with each item still observable and executable.
- F9: The changelog must record the hardening changes and the validation commands used.

## Non-Functional Requirements

- N1: Backward compatibility: existing config files with only plaintext API keys must keep working.
- N2: Safety: test output and documentation must not reveal the actual local API key value.
- N3: No behavior drift: existing six tools, protocol adapters, and pure text chat behavior must remain unchanged except for the key-resolution precedence.
- N4: Testability: new acceptance scenarios must run without live network access or a real LLM.
- N5: CI friendliness: automated checks must not require interactive TUI use.
- N6: Documentation clarity: manual and real API checks must be clearly marked so they are not confused with automated test failures.

## Out of Scope

- No removal of plaintext API-key support.
- No migration tool for existing config files.
- No secret manager integration beyond environment-variable override.
- No live API end-to-end test requirement.
- No new tools beyond ReadFile, WriteFile, EditFile, Bash, Glob, and Grep.
- No Agent Loop or multi-step autonomous execution.
- No permission sandbox, command approval dialog, or rollback mechanism.
- No redesign of the TUI layout.

## Acceptance Criteria

- AC1: When both an environment key and a plaintext config key are present, the runtime client uses the environment value.
- AC2: When no environment key is present, the runtime client still uses the plaintext config key from existing config.
- AC3: A config/documentation example shows the environment-first behavior and does not include a real secret.
- AC4: A Chinese-character scan over the tool implementation directory returns no matches.
- AC5: A focused model-visible language check proves the tool system prompt, tool names, tool descriptions, and tool schemas contain no Chinese characters.
- AC6: Automated TUI trace tests observe pending, success, and error tool-call states.
- AC7: Automated single-step flow tests prove the conversation sequence for successful ReadFile is user -> assistant(tool call) -> tool -> assistant(final).
- AC8: Automated single-step flow tests prove a missing file becomes a tool error result and still reaches a final assistant reply.
- AC9: Automated single-step flow tests prove a Bash command result is returned to the model and the final reply is produced.
- AC10: Automated single-step flow tests prove tool calls emitted in the second model response are ignored.
- AC11: Automated pure-chat regression proves no tool result is added when the model returns only text.
- AC12: Payload construction tests prove the request includes the tool system prompt and enabled tool descriptions, and excludes tool metadata from model-visible messages.
- AC13: The reorganized checklist separates automated, manual TUI, and real API checks, and every item has a concrete verification method.
- AC14: The full automated test suite passes after the changes.
- AC15: The changelog includes the files changed, tests added, and validation result.
