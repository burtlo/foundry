# `visit examine complete`

Status: **implemented**

Seal agent receipt and transition after accepted examination judgment.

## Invocation

```bash
foundry visit examine complete [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--visit` | no | — | Visit id (default: active visit) |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--summary` | no | — | Short summary for visit transition on success |
| `--with-open-questions` | no | false | Allow transition to shape.examine.gate while clarifying questions remain open |
| `--revision` | no | — | Expected snapshot revision before commit |

## Acceptance

[shape_examine.feature](../../.cursor/foundry/cli/tests/acceptance/features/shape_examine.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
