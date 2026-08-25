# Engineering Baseline And Documentation Alignment Tasks

## Task 1: Establish The Verified Local Environment

1. Create a project-local virtual environment outside version control.
2. Install the project in editable mode with the `dev` extra.
3. Record the exact Python and dependency versions used for verification.
4. Run package import and CLI version checks.

Dependencies: none.

Verification:

- `python -c "import mewcode"` succeeds.
- `mewcode --version` succeeds.
- `python -m mewcode --version` succeeds.

## Task 2: Add Reproducible Continuous Integration

1. Create `.github/workflows/tests.yml`.
2. Configure pull request and push triggers.
3. Test Python 3.10, 3.11, 3.12, and 3.13.
4. Install with `python -m pip install -e ".[dev]"`.
5. Run `python -m pytest`.

Dependencies: Task 1 confirms the intended installation contract.

Verification:

- Workflow YAML is syntactically valid.
- The workflow has no manually exported `PYTHONPATH`.
- Matrix versions match the package support contract.

## Task 3: Align Public Setup And Capability Documentation

1. Update `README.md` installation, test, and platform-neutral launch
   instructions.
2. Update `MANUAL.md` setup and command documentation.
3. Describe integrated context management, project memory, and opt-in security
   correctly.
4. Label MCP, Skills, Hooks, task orchestration, Worktrees, and Agent Teams as
   foundation-only until an end-to-end user workflow exists.
5. Remove contradictory historical feature claims where they would mislead a
   new user.

Dependencies: Task 1 establishes commands; source inspection establishes
feature states.

Verification:

- No user-facing document contains the obsolete `E:\\agent_class\\project`
  path.
- Commands match actual CLI entry points and package metadata.
- No document calls an unreachable module a complete feature.

## Task 4: Align Contributor Instructions And Roadmap

1. Update `AGENTS.md` with repository-relative setup, test, and TUI flow
   instructions.
2. Update `spec.md` roadmap status based on actual user-accessible behavior.
3. Preserve the existing requirement for spec-first, approval-gated changes.
4. Do not modify `CLAUDE.md` unless it must remain identical to `AGENTS.md` for
   consistency; if changed, apply the same factual corrections.

Dependencies: Task 3 defines the capability vocabulary.

Verification:

- Contributor instructions use `pip install -e ".[dev]"` and `python -m
  pytest`.
- Roadmap distinguishes implementation from a foundation module.
- No contributor instruction points to a non-repository local path.

## Task 5: Run The Verification Suite

1. Run all tests in the verified local environment.
2. Investigate and fix only baseline/install/documentation issues discovered by
   verification; any behavioral defect becomes a separate spec.
3. Run `git diff --check`.
4. Review the final diff to confirm no application behavior or runtime config
   changes are included beyond the module entry point that delegates to the
   existing CLI.
5. Record outcomes in this phase's checklist and `CHANGELOG.md`.

Dependencies: Tasks 2 through 4.

Verification:

- Full suite passes locally.
- Diff check passes.
- Changed files are documentation, CI, phase records, and CHANGELOG only.
