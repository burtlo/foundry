# `receipt seal`

Status: **implemented**

Validate a receipt draft, fill provenance, and append receipt.linked (capability receipt.link).

## Invocation

```bash
foundry receipt seal [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--visit` | no | — | Visit id (default: active visit) |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--schema` | no | — | Receipt schema registry path |
| `--file` | yes | — | run: or workspace: path to receipt JSON draft |

## Acceptance

[shape_intake.feature](../../.cursor/foundry/cli/tests/acceptance/features/shape_intake.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
