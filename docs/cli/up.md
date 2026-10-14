# `up`

Status: **implemented**

Reconcile judgment bridge and job host; print readiness summary (human or --json).

## Invocation

```bash
foundry up [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--foreground` | no | false | Supervise children; Ctrl+C stops processes started by this invocation |

## Acceptance

[test_foundry_up.py](../../.cursor/foundry/cli/tests/unit/test_foundry_up.py)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
