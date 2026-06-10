# MewCode Token Metrics Checklist

## Document Approval

- [ ] User explicitly approves `specs/05-token-metrics/spec.md`.
- [ ] User explicitly approves `specs/05-token-metrics/plan.md`.
- [ ] User explicitly approves `specs/05-token-metrics/task.md`.
- [ ] User explicitly approves `specs/05-token-metrics/checklist.md`.
- [ ] No implementation code is changed before approval.

## P0: Real Token Usage in UI

- [ ] In `src/mewcode/tui/app.py`, no status bar update passes `event.usage.total_tokens, 0` as the token display source.
- [ ] In `src/mewcode/tui/widgets/status_bar.py`, token display does not use the old fake `used/total` shape for aggregate totals.
- [ ] A fake usage event with `prompt_tokens=10`, `completion_tokens=20`, `total_tokens=30` makes the status bar display total `30`.
- [ ] The same fake usage event makes prompt `10` and completion `20` observable in wide status formatting.
- [ ] A provider response without usage displays `N/A` for usage-dependent values instead of `0`.
- [ ] Existing `tests/test_agent_events.py` usage event tests still pass or are replaced by equivalent metrics event coverage.

## P0: Adapter Usage Capture

- [ ] OpenAI-compatible streaming requests include `stream_options.include_usage = true` where supported.
- [ ] OpenAI-compatible final streaming usage `{prompt_tokens: 10, completion_tokens: 20, total_tokens: 30}` yields `TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)`.
- [ ] Custom OpenAI-compatible streaming parses the same usage object into the same `TokenUsage`.
- [ ] Custom streaming without a usage object yields `token_usage is None`, not `TokenUsage(0, 0, 0)`.
- [ ] Claude streaming usage maps input tokens to prompt tokens.
- [ ] Claude streaming usage maps output tokens to completion tokens.
- [ ] Ollama final prompt and generation counters map to prompt and completion tokens.
- [ ] Adapter tool-call streaming tests still pass after usage changes.

## P1: Average API Speed

- [ ] A fake call with `completion_tokens=20` and output duration `2.0s` reports `10.0 tok/s`.
- [ ] A fake call with no completion token usage does not add a speed sample.
- [ ] Two calls with speeds `10.0 tok/s` and `30.0 tok/s` report average `20.0 tok/s`.
- [ ] The status bar wide format contains the literal text `tok/s` when speed is available.
- [ ] The status bar displays `N/A` for speed when no speed samples exist.

## P1: Average First Token Latency

- [ ] A fake stream whose first non-empty text chunk arrives `0.5s` after request start reports `TTFT = 500ms`.
- [ ] A fake stream with no non-empty text chunk does not add a TTFT sample.
- [ ] Two calls with TTFT `500ms` and `1500ms` report average `1000ms`.
- [ ] The status bar wide format contains the literal text `TTFT` when TTFT is available.
- [ ] The status bar displays `N/A` for TTFT when no TTFT samples exist.

## P1: Average Total Latency

- [ ] A fake stream completing `2.5s` after request start reports `latency = 2500ms`.
- [ ] Two completed calls with latency `1000ms` and `3000ms` report average `2000ms`.
- [ ] Failed or cancelled calls do not corrupt the completed-call latency average.
- [ ] The status bar wide format contains `Lat` or `Latency` when latency is available.
- [ ] The status bar displays `N/A` for latency when no latency samples exist.

## P2: Session Persistence

- [ ] `Message.to_dict()` includes `token_usage` when a message has usage.
- [ ] `Message.from_dict()` restores `token_usage` from a saved dict.
- [ ] Conversation serialization includes existing `total_token_usage`.
- [ ] Conversation serialization includes aggregate API metrics under a stable key such as `api_metrics`.
- [ ] Saved YAML after a fake call with usage contains nonzero `total_token_usage.total_tokens`.
- [ ] Saved YAML after a fake call with metrics contains nonzero API call count.
- [ ] Reloading the saved YAML restores token totals.
- [ ] Reloading the saved YAML restores average speed, average TTFT, and average latency.
- [ ] Loading an old session YAML without `api_metrics` does not raise an exception.

## P2: Narrow Status Bar

- [ ] Wide status formatting includes model, tokens, speed, TTFT, latency, duration, working directory, agent status, and mode.
- [ ] Narrow status formatting includes model, compact tokens, at least one compact performance metric when available, and agent status.
- [ ] Narrow status formatting does not include the full working directory.
- [ ] A long working directory does not push token or agent status text out of the visible narrow format in formatting tests.
- [ ] Compact token formatting converts `1240` into a short form such as `1.2k` or another documented compact equivalent.

## Tests

- [ ] `python -m pytest tests/test_metrics_models.py -v -p no:cacheprovider` passes.
- [ ] `python -m pytest tests/test_agent_events.py -v -p no:cacheprovider` passes.
- [ ] `python -m pytest tests/test_agent_loop_metrics.py -v -p no:cacheprovider` passes.
- [ ] `python -m pytest tests/test_status_bar_metrics.py -v -p no:cacheprovider` passes.
- [ ] `python -m pytest tests/test_tui_metrics.py -v -p no:cacheprovider` passes.
- [ ] `python -m pytest tests/test_conversation_metrics.py -v -p no:cacheprovider` passes.
- [ ] `python -m pytest tests/test_agent_loop.py tests/test_tui_agent_loop.py tests/test_input_box.py -v -p no:cacheprovider` passes.
- [ ] `python -m pytest tests/test_message_tool_calls.py tests/test_adapter_tool_calls.py tests/test_adapter_anthropic_tool_use.py -v -p no:cacheprovider` passes.
- [ ] `python -m pytest tests -v -p no:cacheprovider` passes or every failure is documented with exact failing test names and reason.

## Manual End-to-End Acceptance

- [ ] Start MewCode with `mewcode` from a fresh CMD.
- [ ] Send a prompt to a provider that returns usage.
- [ ] During or after the response, the status bar shows a real token total instead of `/0`.
- [ ] The status bar shows `tok/s`, TTFT, and latency values after at least one completed response with usage and streamed text.
- [ ] Send a prompt through a provider or fake path with no usage; usage-dependent fields show `N/A` instead of fake zeros.
- [ ] Save the session.
- [ ] Open the saved YAML under `%USERPROFILE%\.mewcode\sessions\` and confirm `total_token_usage` and API metrics are present.
- [ ] Restart MewCode and reload or continue the session.
- [ ] Restored status or internal conversation state contains the previously saved token and metrics aggregate.
- [ ] Resize the terminal to a narrow width and verify the status bar remains readable.
