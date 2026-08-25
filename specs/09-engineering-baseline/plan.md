# Engineering Baseline And Documentation Alignment Plan

## Decisions

- Use the existing PEP 517/621 metadata in `pyproject.toml` as the single
  dependency source of truth. Contributors and CI install with
  `pip install -e ".[dev]"`.
- Add GitHub Actions for Python 3.10 through 3.13, matching the declared
  `requires-python = ">=3.10"` contract.
- Keep the test invocation as `python -m pytest`; editable installation makes
  the `src/` package importable without a machine-specific `PYTHONPATH`.
- Treat the current implementation as three states in documentation:
  integrated, opt-in integrated, and foundation-only. Do not imply a feature
  is usable merely because a supporting module exists.
- Add a minimal `__main__.py` that imports and calls the existing `main()`;
  this keeps the console-script and module invocations equivalent.

## Changes

| Area | Change | Rationale |
| --- | --- | --- |
| `README.md` | Replace Windows-specific startup guidance with platform-neutral installation, test, and launch commands; update feature and architecture descriptions. | Make the public entry point runnable and accurate. |
| `MANUAL.md` | Align setup, command reference, security, memory, and current capability boundaries with the application. | Keep operational documentation consistent with README and code. |
| `AGENTS.md` | Replace stale paths and TUI layout information with repository-relative commands and current architecture. | Give coding agents an accurate working contract. |
| `spec.md` | Update the roadmap and capability status without claiming foundation-only modules are finished features. | Preserve the roadmap as a trustworthy source of intent. |
| `.github/workflows/tests.yml` | Install the package with development extras and run the full suite across supported Python versions. | Detect installation and compatibility regressions. |
| `src/mewcode/__main__.py` | Delegate module execution to the existing CLI entry point. | Support the documented `python -m mewcode` command. |

## Verification

1. Create a clean virtual environment.
2. Install the project using `pip install -e ".[dev]"`.
3. Run `python -c "import mewcode"`.
4. Run `mewcode --version` and `python -m mewcode --version`.
5. Run `python -m pytest`.
6. Run `git diff --check`.
7. Review documentation claims against code paths in the TUI, Agent Loop,
   security gateway, context modules, MCP modules, extensions, and
   orchestration modules.

## Risks And Mitigations

- Python 3.13 compatibility may expose third-party dependency constraints.
  CI reports the supported matrix explicitly; package constraints are changed
  only if verification proves they are necessary.
- TUI startup is interactive and provider-dependent. Baseline verification
  checks entry point resolution rather than requiring an API credential or a
  terminal session.
- Documentation updates could overstate unfinished extensions. Every feature
  label is based on whether a user can access it through the current app,
  rather than whether an isolated module exists.
