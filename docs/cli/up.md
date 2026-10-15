# `up`

Status: **implemented**

Reconcile judgment bridge and job host for this workspace; print a verdict-first readiness summary (human or --json). Use -v/--verbose for per-dimension detail.

## Invocation

```bash
foundry up [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--foreground` | no | false | Supervise children; Ctrl+C stops processes started by this invocation |
| `-v`, `--verbose` | no | false | Print per-dimension readiness detail |

## Acceptance

[test_foundry_up.py](../../.cursor/foundry/cli/tests/unit/test_foundry_up.py)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
