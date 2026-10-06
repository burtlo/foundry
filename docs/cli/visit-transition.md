# `visit transition`

Status: **implemented**

Request close on an opened visit; run on_close and on_seal hooks and route when sealed.

## Invocation

```bash
foundry visit transition [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--visit` | no | — | Visit id (default: active visit) |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--summary` | no | — | Short steward summary |
| `--revision` | no | — | Expected snapshot revision before commit |

## Acceptance

[shape_intake.feature](../../.cursor/foundry/cli/tests/acceptance/features/shape_intake.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
