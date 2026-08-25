# Engineering Baseline And Documentation Alignment

## Background

MewCode uses a `src/` package layout and declares runtime and development
dependencies in `pyproject.toml`, but the current developer instructions do
not provide a reproducible installation path. The current environment cannot
collect the suite without package-path setup and misses declared development
dependencies. Project documentation also describes several implemented
capabilities as pending, while newer capability foundations are not accurately
classified as integrated versus standalone.

## Goal

Make the repository reproducibly installable and testable from a clean Python
environment, and make its user and contributor documentation describe the
current product truthfully.

## In Scope

- Document the supported development installation and test commands.
- Add the missing module entry point so `python -m mewcode` delegates to the
  existing CLI.
- Add CI that installs the declared development dependencies and executes the
  test suite on a supported Python version.
- Correct stale local paths, TUI flow descriptions, commands, architecture
  descriptions, and feature-status claims in `README.md`, `MANUAL.md`,
  `AGENTS.md`, and `spec.md`.
- Distinguish production-integrated capabilities from foundations that are not
  yet exposed through the application.
- Verify package imports and the full test suite in an isolated project
  environment.

## Out Of Scope

- Changing runtime Agent behavior, provider adapters, or TUI behavior.
- Changing security defaults or permission policy.
- Implementing MCP server transport, file-backed Skills, Hooks, SubAgents,
  Worktrees, or Agent Teams.
- Adding new product features.

## Acceptance Criteria

1. A fresh supported Python environment can install MewCode with its
   development dependencies using documented commands.
2. `mewcode` and `python -m mewcode` resolve the local package after the
   documented installation.
3. CI installs from the project metadata and runs `pytest` without relying on
   a manually exported `PYTHONPATH`.
4. The test suite passes in the supported CI environment.
5. Documentation no longer describes implemented security, context, and
   project-memory behavior as unimplemented.
6. Documentation labels MCP, Skill, Hook, task orchestration, Worktree, and
   Agent Team code as foundations until they have an end-to-end application
   integration.
7. No Agent, provider, TUI, or runtime configuration behavior changes occur
   in this phase beyond exposing the existing CLI through a module entry point.
