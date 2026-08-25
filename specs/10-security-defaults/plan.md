# Plan

- Change only the shipped `config.yaml` default from `security.enabled: false`
  to `true`; the existing gateway already has default-deny semantics for all
  non-read operations.
- Add regression coverage for the default TUI gateway construction and the
  unchanged read-only policy.
- Update public documentation and the roadmap so the default and opt-out are
  explicit.
- Do not broaden the gateway into a sandbox, diff preview, or command parser
  in this phase.
