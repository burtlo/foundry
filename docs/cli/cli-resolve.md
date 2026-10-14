# `cli resolve`

Status: **implemented**

Resolve foundry bundle paths (registry root, workspace, registry_source, foundry_config_path, and cli_path). Resolution order: --registry, FOUNDRY_REGISTRY, .foundry/foundry.yaml, workspace bundle walk.

## Invocation

```bash
foundry cli resolve [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

_No command-specific flags._

## Acceptance

[foundry_config.feature](../../.cursor/foundry/cli/tests/acceptance/features/foundry_config.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
