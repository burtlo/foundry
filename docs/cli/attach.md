# `attach`

Status: **implemented**

Stream ledger events for supervision; detach leaves the run running.

## Invocation

```bash
foundry attach [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `run` | yes | — | Run id |
| `--after-seq` | no | 0 | Stream events with seq > after-seq |
| `--no-follow` | no | false | Print snapshot (and events with --json) without streaming |
| `--local` | no | false | Use disk reads even when the job host is running |

## Acceptance

[user_cli.feature](../../.cursor/foundry/cli/tests/acceptance/features/user_cli.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
