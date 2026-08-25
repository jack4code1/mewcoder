# Consistent Slash Command Catalog

## Goal

Use one command registry for command completion and help output.

## Scope

- Register all supported public and security command forms.
- Generate `/help` from registered command definitions.
- Preserve existing hard-coded dispatch behavior.

## Acceptance Criteria

- Help and completion include the same command names.
- Security approval request commands appear in help.
- Existing command behavior remains unchanged.
