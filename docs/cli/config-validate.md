# `config validate`

Status: **implemented**

Validate `.foundry/foundry.yaml` against `foundry-config.schema.json` and verify the registry path resolves to a bundle.

## Invocation

```bash
foundry config validate [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

_No command-specific flags._

## Acceptance

[foundry_config.feature](../../.cursor/foundry/cli/tests/acceptance/features/foundry_config.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
