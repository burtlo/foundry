# `dev engine-matrix`

Status: **implemented**

Generate the implementation-flow node runtime matrix at `docs/generated/engine-node-runtime-matrix.md` (engine DSL inventory).

## Invocation

```bash
foundry dev engine-matrix [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--flow` | no | implementation | Flow id (default: implementation) |
| `--output` | no | — | Output markdown path (default: docs/generated/engine-node-runtime-matrix.md) |

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
