# `visit record complete`

Status: **implemented**

Publish plan and transition after accepted record judgment.

## Invocation

```bash
foundry visit record complete [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--visit` | no | — | Visit id (default: active visit) |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--summary` | no | — | Short summary for visit transition on success |
| `--revision` | no | — | Expected snapshot revision before commit |

## Acceptance

[shape_record.feature](../../tests/acceptance/features/shape_record.feature)

## Implementation

[foundry.py](../../foundry.py)
