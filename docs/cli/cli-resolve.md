# `cli resolve`

Status: **implemented**

Resolve foundry bundle paths (registry root, workspace, registry_source, foundry_config_path, and cli_path). Resolution order: --registry, FOUNDRY_REGISTRY, .foundry/foundry.yaml, workspace bundle walk.

## Invocation

```bash
foundry --json cli resolve [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Response fields

| Field | Description |
|---|---|
| `registry_root` | Resolved Foundry bundle (`.cursor/foundry`) |
| `workspace` | Application workspace root |
| `registry_source` | How the bundle was resolved (`cli_flag`, `env`, `foundry.yaml`, `workspace_bundle`) |
| `foundry_config_path` | Path to `.foundry/foundry.yaml` when present |
| `cli_path` | Path to `foundry.sh` for the resolved bundle — relative to workspace when possible, otherwise absolute. Derived from `{registry_root}/cli/foundry.sh`. |

## Command flags

_No command-specific flags._

## Acceptance

[foundry_config.feature](../../.cursor/foundry/cli/tests/acceptance/features/foundry_config.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
