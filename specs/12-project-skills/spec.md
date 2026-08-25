# File-Based Project Skills

## Goal

Make project-local Markdown skill files discoverable and available to every
Agent request without requiring application code changes per skill.

## Scope

- Discover `*.md` files under `.mewcode/skills/` in the current workspace.
- Use the filename stem as the stable skill name and file body as instructions.
- Inject discovered skills as labelled system context before conversation
  history.
- Add `/skills` to list active skills and their source paths.

## Acceptance Criteria

- Adding a Markdown file makes the skill available to the next request.
- Missing skill directories are harmless.
- `/skills` shows discovered names and reports an empty collection clearly.
- Existing memory and context ordering is retained.
