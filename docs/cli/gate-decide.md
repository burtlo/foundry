# `gate decide`

Status: **implemented**

Record the authorized decision on an opened user gate and request close. Appends gate.resolved, seals the visit, and routes by connection on.decisions.

## Invocation

```bash
foundry gate decide [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--visit` | no | — | Visit id (default: active gate visit) |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--decision` | yes | — | One of the gate produces.options values |
| `--revision` | no | — | Expected snapshot revision before commit |

## Acceptance

[shape_examine_gate.feature](../../.cursor/foundry/cli/tests/acceptance/features/shape_examine_gate.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
