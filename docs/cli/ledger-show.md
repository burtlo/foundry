# `ledger show`

Status: **implemented**

Read ledger events from the run snapshot (read-only).

## Invocation

```bash
foundry ledger show [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--from-seq` | no | — | First sequence number (inclusive) |
| `--to-seq` | no | — | Last sequence number (inclusive) |
| `--types` | no | — | Comma-separated event type filter |

## Acceptance

[shape_intake.feature](../../.cursor/foundry/cli/tests/acceptance/features/shape_intake.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
