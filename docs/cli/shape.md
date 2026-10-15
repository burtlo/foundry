# `shape`

Status: **implemented**

Create a run from a shape request, complete shape.intake, and return immediately with run id plus attach/status hints while the host continues examine. Use --attach to stream ledger events through clarifying questions.

## Invocation

```bash
foundry shape [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--input`, `--prompt` | no | — | Verbatim shape request text |
| `--input-file` | no | — | Path to a file containing the shape request |
| `--flow` | no | — | Flow id (default: implementation) |
| `--run-id` | no | — | Explicit run id slug |
| `--no-host` | no | false | Do not auto-start the job host; advance on disk when host is not running |
| `--local` | no | false | Use disk/engine directly even when the job host is running |
| `--attach` | no | false | After intake handoff, stream run ledger events (same as foundry attach) |

## Acceptance

[user_cli.feature](../../.cursor/foundry/cli/tests/acceptance/features/user_cli.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
