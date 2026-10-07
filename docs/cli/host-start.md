# `host start`

Status: **implemented**

Start the background job host for this workspace.

## Invocation

```bash
foundry host start [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--auto-advance` | no | false | Enable background auto-advance for runs without human waits |
| `--auto-advance-interval` | no | 2.0 | Seconds between auto-advance scans when --auto-advance is set |

## Acceptance

[job_host.feature](../../.cursor/foundry/cli/tests/acceptance/features/job_host.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
