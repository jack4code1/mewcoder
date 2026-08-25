# Safe-By-Default Tool Execution

## Goal

Make approval-gated execution the default for state-changing Agent tools while
preserving automatic use of read-only tools.

## Scope

- Enable the existing security gateway by default in the shipped configuration.
- Require approval for file writes, file edits, shell commands, and external
  tools; retain automatic execution for reads and searches.
- Keep once, session, and project grants, audit records, cancellation, and
  timeout behavior intact.
- Correct user documentation to state that safety is enabled by default and
  can be explicitly disabled for trusted automation.

## Acceptance Criteria

- A default TUI session creates an execution gateway.
- Read-only tools execute without an approval request.
- State-changing tools do not execute until approved.
- Existing `/approve`, `/deny`, request approval, and `/audit` paths remain
  functional.
- Security tests and the full suite pass.
