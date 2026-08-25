# Plan

- Keep `ProjectMemoryStore` unchanged; records already have stable IDs and
  kinds.
- Format existing data as `id [kind]: content` in the TUI command handler.
- Reorder `_messages_with_system()` to produce system prompt, memories, then
  conversation messages.
- Test behavior through the TUI helper and request-message construction.
