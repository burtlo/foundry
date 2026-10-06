# `run events`

Status: **implemented**

Return ledger events after a sequence number.

## Invocation

```bash
foundry run events [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--after-seq` | no | 0 | Return events with seq > after_seq |
| `--local` | no | false | Read from disk when host is running |

## Acceptance

[job_host.feature](../../.cursor/foundry/cli/tests/acceptance/features/job_host.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
