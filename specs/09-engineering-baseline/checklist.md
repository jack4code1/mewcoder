# Engineering Baseline And Documentation Alignment Checklist

## Installation

- [x] A clean supported Python environment installs `mewcode` with
  `pip install -e ".[dev]"`.
- [x] `import mewcode` succeeds after the documented install.
- [x] `mewcode --version` succeeds after the documented install.
- [x] `python -m mewcode --version` succeeds after the documented install.

## CI

- [x] GitHub Actions is configured for pushes and pull requests.
- [x] CI is configured to test Python 3.10, 3.11, 3.12, and 3.13.
- [x] CI installs the package using project metadata and the `dev` extra.
- [x] CI runs `python -m pytest` without `PYTHONPATH` setup.

## Documentation

- [x] README documents reproducible installation, testing, and launch steps.
- [x] MANUAL commands match the application's actual commands.
- [x] AGENTS uses repository-relative paths and current TUI flow.
- [x] Documentation accurately marks context management and project memory as
  integrated.
- [x] Documentation accurately marks security approvals as opt-in.
- [x] Documentation labels MCP, Skills, Hooks, task orchestration, Worktrees,
  and Agent Teams as foundations rather than complete workflows.
- [x] Obsolete local Windows paths are removed from maintained user and
  contributor documentation.

## Regression Safety

- [x] `python -m pytest` passes in the verified environment.
- [x] `git diff --check` passes.
- [x] No application behavior or runtime configuration changes are included
  beyond the module entry point that delegates to the existing CLI.
- [x] CHANGELOG records the baseline and documentation update.
