# MewCode Tools Hardening Checklist

> Every item must be verified by command output or observable behavior. Automated checks do not require a live LLM or interactive TUI.

## Automated Checks

- [ ] Config lookup uses environment value before plaintext fallback.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_config_env.py::test_api_key_env_overrides_plaintext -v
  ```
  Expected: test passes.

- [ ] Config lookup uses plaintext `api_key` when the configured environment variable is absent.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_config_env.py::test_plaintext_api_key_used_when_env_missing -v
  ```
  Expected: test passes.

- [ ] Config lookup uses plaintext `api_key` when the configured environment variable is present but empty.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_config_env.py::test_empty_env_value_falls_back_to_plaintext -v
  ```
  Expected: test passes.

- [ ] Config lookup does not mutate the original loaded config dictionary.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_config_env.py::test_get_model_config_does_not_mutate_source_config -v
  ```
  Expected: test passes.

- [ ] TUI tool trace pending state renders `→`, tool name, and parameter summary.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_tui_tool_trace.py::test_tool_trace_pending_state -v
  ```
  Expected: test passes.

- [ ] TUI tool trace success state renders `✓`, tool name, and success summary.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_tui_tool_trace.py::test_tool_trace_success_state -v
  ```
  Expected: test passes.

- [ ] TUI tool trace error state renders `✗`, tool name, and error summary.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_tui_tool_trace.py::test_tool_trace_error_state -v
  ```
  Expected: test passes.

- [ ] Mock ReadFile success flow produces conversation roles `user, assistant, tool, assistant`, and the tool result is not an error.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_tui_tool_flow.py::test_read_file_success_flow -v
  ```
  Expected: test passes.

- [ ] Mock missing-file flow records a tool error and still reaches a final assistant reply.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_tui_tool_flow.py::test_missing_file_flow_returns_tool_error_and_final_reply -v
  ```
  Expected: test passes.

- [ ] Mock Bash flow returns command output and reaches a final assistant reply.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_tui_tool_flow.py::test_bash_flow_returns_output_and_final_reply -v
  ```
  Expected: test passes.

- [ ] Tool calls emitted by the second model response are ignored and no second tool result is added.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_tui_tool_flow.py::test_second_response_tool_calls_are_ignored -v
  ```
  Expected: test passes.

- [ ] Pure-chat flow adds no tool result message.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_tui_tool_flow.py::test_pure_chat_flow_adds_no_tool_result -v
  ```
  Expected: test passes.

- [ ] Payload construction includes the tool system prompt in model-visible messages.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_payload_language.py::test_payload_contains_tool_system_prompt -v
  ```
  Expected: test passes.

- [ ] Payload construction includes enabled tool descriptions.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_payload_language.py::test_payload_contains_enabled_tool_descriptions -v
  ```
  Expected: test passes.

- [ ] Tool metadata is not present in model-visible payload messages.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_payload_language.py::test_tool_metadata_is_not_serialized_to_payload -v
  ```
  Expected: test passes.

- [ ] Model-visible system prompt, tool names, tool descriptions, and tool schemas contain no Chinese characters.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_payload_language.py::test_model_visible_tool_strings_have_no_chinese_characters -v
  ```
  Expected: test passes.

## Static Scans

- [ ] Tool implementation directory contains no Chinese characters.
  Verification:
  ```powershell
  rg "[\p{Han}]" src\mewcode\engine\tools
  ```
  Expected: no output.

- [ ] `api_key_env` appears in runtime config and user-facing docs.
  Verification:
  ```powershell
  rg "api_key_env" config.yaml README.md MANUAL.md
  ```
  Expected: at least one match in each listed file.

- [ ] Documentation examples use placeholder values, not local real secrets.
  Verification:
  ```powershell
  rg "your-api-key|your-api-endpoint|MIMO_API_KEY" README.md MANUAL.md
  ```
  Expected: placeholder matches are present.

- [ ] Documentation and tests do not print the local real API key.
  Verification:
  ```powershell
  rg "tp-" README.md MANUAL.md tests
  ```
  Expected: no output.

## Config Integration

- [ ] Current configured model keeps plaintext fallback available.
  Verification:
  ```powershell
  rg "api_key:" config.yaml
  ```
  Expected: existing plaintext `api_key` field is still present.

- [ ] Current configured model has an optional environment override field.
  Verification:
  ```powershell
  rg "api_key_env:" config.yaml
  ```
  Expected: `api_key_env` is present.

- [ ] Runtime app still receives resolved credentials through model config lookup, with no adapter-specific environment handling.
  Verification:
  ```powershell
  rg "get_model_config|api_key_env|os.environ|getenv" src\mewcode\config.py src\mewcode\tui\app.py src\mewcode\engine\adapters
  ```
  Expected: environment lookup appears in config resolution, not inside individual adapters.

## Manual TUI Checks

- [ ] Manual ReadFile flow shows visible tool trace and final reply.
  Verification:
  ```powershell
  .\start.ps1
  ```
  Then input: `读一下 config.yaml 然后告诉我默认模型是什么`
  Expected: TUI shows `→ ReadFile(...)`, then `✓ ReadFile(...)`, then a final reply mentioning `mimo-v2.5-pro`.

- [ ] Manual missing-file flow shows error trace and final reply.
  Verification:
  ```powershell
  .\start.ps1
  ```
  Then input: `读一下 missing-file-xyz.txt`
  Expected: TUI shows `→ ReadFile(...)`, then `✗ ReadFile(...): File not found...`, then a final reply explaining the file is missing.

- [ ] Manual pure-chat flow does not show tool trace.
  Verification:
  ```powershell
  .\start.ps1
  ```
  Then input: `你好，介绍一下自己`
  Expected: no `→`, `✓`, or `✗` tool trace rows appear.

## Real API Checks

- [ ] Optional live API check uses environment key when present.
  Verification:
  ```powershell
  $env:MIMO_API_KEY="your-real-key-in-local-shell"
  .\start.ps1
  ```
  Expected: the configured model can respond without relying on the plaintext key. Do not print the real key.

- [ ] Optional live API check falls back to plaintext key when environment key is absent.
  Verification:
  ```powershell
  Remove-Item Env:\MIMO_API_KEY -ErrorAction SilentlyContinue
  .\start.ps1
  ```
  Expected: the configured model can still respond using the existing plaintext fallback. Do not print the real key.

## Final Regression

- [ ] New focused tests pass together.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/test_config_env.py tests/test_tui_tool_trace.py tests/test_tui_tool_flow.py tests/test_payload_language.py -v
  ```
  Expected: all selected tests pass.

- [ ] Full automated suite passes.
  Verification:
  ```powershell
  $env:PYTHONPATH="E:\agent_class\project\src"
  python -m pytest tests/ -v
  ```
  Expected: all tests pass.

- [ ] CHANGELOG records hardening changes and validation commands.
  Verification:
  ```powershell
  rg "03-tools-hardening|api_key_env|test_tui_tool_flow|test_payload_language" CHANGELOG.md
  ```
  Expected: all terms are present.

- [ ] Worktree contains only intended files for this hardening chapter.
  Verification:
  ```powershell
  git -c core.excludesfile= status --short
  ```
  Expected: changed files match the approved task file list.
