# `run get`

Status: **implemented**

Inspect run snapshot summary via host or disk.

## Invocation

```bash
foundry run get [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--local` | no | false | Read snapshot from disk even when the job host is running |

## Acceptance

[job_host.feature](../../.cursor/foundry/cli/tests/acceptance/features/job_host.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
