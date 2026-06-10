# MewCode Tools Hardening Tasks

> Based on approved `spec.md` and `plan.md`.

## File List

| Operation | File | Responsibility |
|-----------|------|----------------|
| Modify | `src/mewcode/config.py` | Resolve API key from environment first, plaintext fallback second |
| Modify | `config.yaml` | Add optional environment-variable key name while preserving existing plaintext key |
| Modify | `README.md` | Document environment-first API-key behavior with placeholder examples |
| Modify | `MANUAL.md` | Document environment-first API-key behavior with placeholder examples |
| Modify | `src/mewcode/engine/tools/system_prompt.py` | Remove non-English doc/comment text from tool implementation directory |
| Add | `tests/test_config_env.py` | Config precedence and fallback tests |
| Add | `tests/test_tui_tool_trace.py` | Tool trace pending/success/error rendering tests |
| Add | `tests/test_tui_tool_flow.py` | Mock single-step flow tests |
| Add | `tests/test_payload_language.py` | Payload construction and language-policy tests |
| Add | `specs/03-tools-hardening/checklist.md` | Reorganized acceptance checklist |
| Modify | `CHANGELOG.md` | Record implementation and validation result after development |

---

## T1: Add Environment-First API Key Resolution

**Files:** `src/mewcode/config.py`
**Depends on:** none
**References:** `get_model_config()` in `src/mewcode/config.py`; `_ensure_llm_client()` in `src/mewcode/tui/app.py`

**Steps:**
1. Import `os`.
2. Change model config lookup so it returns a shallow copy of the model config instead of the original nested dictionary.
3. Read optional `api_key_env` from the copied model config.
4. If `api_key_env` names a non-empty environment variable, replace the copied config's `api_key` value with that environment value.
5. If the environment variable is missing or empty, keep the existing plaintext `api_key` value unchanged.
6. Do not change the return type or existing caller contract.

**Verification:**
Run a small import probe:

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -c "from mewcode.config import get_model_config; print(get_model_config({'llm': {'models': {'m': {'api_key': 'plain'}}}}, 'm')['api_key'])"
```

Expected output: `plain`

---

## T2: Add Config Resolution Tests

**Files:** `tests/test_config_env.py`
**Depends on:** T1
**References:** `get_model_config()` in `src/mewcode/config.py`

**Steps:**
1. Add a test where both plaintext key and environment variable are present; assert returned `api_key` equals the environment value.
2. Add a test where `api_key_env` is configured but the environment variable is absent; assert returned `api_key` equals the plaintext value.
3. Add a test where the environment variable is present but empty; assert plaintext fallback is used.
4. Add a test proving the original nested config dictionary is not mutated by lookup.
5. Use pytest `monkeypatch` for environment setup.
6. Do not print or assert any real local secret.

**Verification:**

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/test_config_env.py -v
```

Expected result: all tests pass.

---

## T3: Document Environment-First Configuration

**Files:** `config.yaml`, `README.md`, `MANUAL.md`
**Depends on:** T1
**References:** config examples in `README.md` and `MANUAL.md`

**Steps:**
1. Add an optional `api_key_env` field to the configured model in `config.yaml`.
2. Preserve the existing plaintext `api_key` field.
3. Update README configuration examples to show `api_key_env` and a placeholder plaintext fallback.
4. Update MANUAL configuration examples with the same environment-first behavior.
5. Ensure documentation examples use placeholder values only.
6. Do not remove the user's existing plaintext runtime config value.

**Verification:**

```powershell
rg "api_key_env" config.yaml README.md MANUAL.md
rg "your-api-key|your-api-endpoint|MIMO_API_KEY" README.md MANUAL.md
```

Expected result: `api_key_env` is documented and examples contain placeholders, not real secrets.

---

## T4: Remove Tool Directory Chinese Scan Hit

**Files:** `src/mewcode/engine/tools/system_prompt.py`
**Depends on:** none
**References:** current docstring in `src/mewcode/engine/tools/system_prompt.py`

**Steps:**
1. Replace the Chinese section-reference text in the module docstring with English wording.
2. Avoid changing the runtime system prompt unless necessary.
3. Do not modify tool names, tool descriptions, schemas, or tool result strings.

**Verification:**

```powershell
rg "[\p{Han}]" src\mewcode\engine\tools
```

Expected result: no output.

---

## T5: Add TUI Tool Trace Tests

**Files:** `tests/test_tui_tool_trace.py`
**Depends on:** none
**References:** `ChatArea.add_tool_call()` and `ChatArea.update_tool_call_result()` in `src/mewcode/tui/widgets/chat_area.py`

**Steps:**
1. Use Textual test mode to mount `MewCodeApp` or the `ChatArea` widget.
2. Exercise pending state by calling `add_tool_call()`.
3. Exercise success state by calling `update_tool_call_result(..., success=True, ...)`.
4. Exercise error state by calling `update_tool_call_result(..., success=False, ...)`.
5. Inspect the supported widget renderable/text state for `→`, `✓`, `✗`, tool name, and summary.
6. Keep the test independent of real LLM calls.

**Verification:**

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/test_tui_tool_trace.py -v
```

Expected result: pending, success, and error trace tests pass.

---

## T6: Add Mock Single-Step Flow Tests

**Files:** `tests/test_tui_tool_flow.py`
**Depends on:** T5
**References:** `_handle_message()` and `_process_with_llm()` in `src/mewcode/tui/app.py`; `ToolCall` and `StreamChunk` in `src/mewcode/engine/models/message.py`

**Steps:**
1. Build fake async LLM clients that implement `chat_stream()` and `close()`.
2. Add ReadFile success scenario: first stream yields a ReadFile tool call, second stream yields final text.
3. Add missing-file scenario: first stream yields ReadFile for a nonexistent file, second stream yields final text.
4. Add Bash scenario: first stream yields Bash for `echo hello world`, second stream yields final text.
5. Add second-response suppression scenario: second stream emits tool calls, and the app ignores them.
6. Add pure-chat scenario: first stream yields only text and no tool result is added.
7. Assert conversation role sequence, tool error flags, tool result content, and fake client call count.
8. Avoid real network and real model calls.

**Verification:**

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/test_tui_tool_flow.py -v
```

Expected result: all fake single-step flow scenarios pass.

---

## T7: Add Payload and Language Policy Tests

**Files:** `tests/test_payload_language.py`
**Depends on:** T1, T4
**References:** `_install_fake_stream()` pattern in `tests/test_adapter_tool_calls.py`; `build_system_prompt()` in `src/mewcode/engine/tools/system_prompt.py`; `ToolRegistry.to_openai_format()` in `src/mewcode/engine/tools/registry.py`

**Steps:**
1. Reuse or locally define a fake stream context manager to capture adapter request payloads.
2. Build a `ToolContext`, default tool registry, and system message.
3. Call an OpenAI-compatible adapter with captured payload and enabled tools.
4. Assert payload contains a system message with working directory, host OS, and English tool guidelines.
5. Assert payload contains enabled tool descriptions.
6. Assert model-visible strings from system prompt, tool names, tool descriptions, and schemas contain no Chinese characters.
7. Add a tool result message with metadata in the project model and assert metadata does not appear in the outgoing payload.

**Verification:**

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/test_payload_language.py -v
```

Expected result: payload and language-policy tests pass.

---

## T8: Reorganize Hardening Checklist

**Files:** `specs/03-tools-hardening/checklist.md`
**Depends on:** T2, T5, T6, T7
**References:** approved `specs/03-tools-hardening/spec.md`; previous test report from `specs/02-tools/checklist.md`

**Steps:**
1. Create checklist sections: automated checks, manual TUI checks, real API checks, documentation/config checks, final regression.
2. Convert every acceptance criterion from spec AC1-AC15 into at least one observable checklist item.
3. For automated items, include concrete pytest or `rg` commands.
4. For manual TUI items, clearly label them as manual.
5. For real API items, clearly label them as optional/live-environment checks.
6. Ensure no item requires printing the local real API key.

**Verification:**

```powershell
rg "Automated|Manual TUI|Real API|python -m pytest|rg" specs\03-tools-hardening\checklist.md
```

Expected result: checklist sections and verification commands are present.

---

## T9: Connect Changes to the Main Runtime Path

**Files:** `src/mewcode/config.py`, `src/mewcode/tui/app.py`, `config.yaml`
**Depends on:** T1, T2, T3
**References:** `_ensure_llm_client()` in `src/mewcode/tui/app.py`; `AdapterFactory.create_client()` call site

**Steps:**
1. Confirm `MewCodeApp` still obtains adapter credentials only through the model config lookup.
2. Confirm no adapter-specific environment lookup was added.
3. Confirm the optional environment field in config is enough for the default configured model.
4. Run a probe with a fake environment value and assert client creation receives the resolved key without exposing it in output.
5. Run a probe with no environment value and assert plaintext fallback still resolves.

**Verification:**

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/test_config_env.py tests/test_tui_tool_flow.py -v
```

Expected result: config behavior and app flow tests pass together.

---

## T10: End-to-End Validation and Changelog

**Files:** `CHANGELOG.md`
**Depends on:** T1-T9
**References:** `pyproject.toml` pytest config; approved checklist in `specs/03-tools-hardening/checklist.md`

**Steps:**
1. Run the new focused tests.
2. Run the full suite.
3. Run the static Chinese-character scan for the tool implementation directory.
4. Run documentation/config search probes for `api_key_env` and placeholder examples.
5. Record validation commands and pass/fail counts in CHANGELOG.
6. Confirm `git status --short` only shows intended changed files.

**Verification:**

```powershell
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/ -v
rg "[\p{Han}]" src\mewcode\engine\tools
git -c core.excludesfile= status --short
```

Expected result:
- Full pytest passes.
- Tool directory Chinese scan has no output.
- Git status shows only this hardening chapter's intended files.

## Execution Order

```text
T1 -> T2 -> T3 -> T9
      |
T4 -> T7

T5 -> T6

T8 depends on T2, T5, T6, T7

T10 depends on T1-T9
```

Parallel-safe groups:
- T2 and T4 can be developed independently after T1 is understood.
- T5 and T7 can be developed independently.
- Documentation work in T3 can proceed while tests are being drafted, as long as final validation runs after all changes.
