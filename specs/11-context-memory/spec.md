# Usable Project Memory Context

## Goal

Make existing project memory records manageable from the TUI and ensure they
are supplied to the model as stable system context before conversation history.

## Scope

- Display memory IDs and kinds in `/memory` output so `/forget <id>` is usable.
- Place project-memory system messages immediately after the generated system
  prompt and before stored conversation messages.
- Add focused regression tests for both behaviors.

## Out Of Scope

- Semantic memory search, automatic extraction, expiry policies, or new
  storage formats.
- LLM-generated conversation summaries.

## Acceptance Criteria

- A user can copy an ID from `/memory` and use it with `/forget`.
- Project memories precede user and assistant history in each request.
- Existing context planning and memory persistence behavior remain intact.
