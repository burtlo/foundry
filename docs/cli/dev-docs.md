# `dev docs`

Status: **implemented**

Build catalog indexes and regenerate all node, worker, and CLI documentation.

## Invocation

```bash
foundry dev docs [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--flow` | no | implementation | Flow id (default: implementation) |
| `--output` | no | — | Output directory (default: docs) |
| `--smoke` | no | false | Generate shape.intake only (fast check; skips index.md) |

## Acceptance

[dev_commands.feature](../../.cursor/foundry/cli/tests/acceptance/features/dev_commands.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
