# `catalog build`

Status: **implemented**

Generate machine-readable node index YAML files from the flow registry.

## Invocation

```bash
foundry catalog build [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--flow` | no | — | Flow id (default: implementation) |
| `--node` | no | — | Build index for a single node id |
| `--output` | no | — | Output directory for index files |

## Acceptance

[catalog_build.feature](../../.cursor/foundry/cli/tests/acceptance/features/catalog_build.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
