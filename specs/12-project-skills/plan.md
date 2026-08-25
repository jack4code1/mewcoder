# Plan

- Add a small filesystem loader alongside `SkillDefinition` and `SkillRunner`.
- Keep parsing intentionally minimal: each UTF-8 Markdown file becomes one
  skill, avoiding a new front-matter format or dependency.
- Re-read files on each request so changes apply immediately.
- Reuse `SkillRunner.context_items()` to build labelled system messages.
