# Plan

Implement newline-delimited JSON-RPC over an asyncio subprocess. Support
`initialize`, `notifications/initialized`, `tools/list`, and `tools/call`.
Register discovered tools with names scoped by server to avoid collisions.
