# `host logs`

Status: **implemented**

Show trailing lines from host or startup log files.

## Invocation

```bash
foundry host logs [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--source` | no | host | Log file: host.log (default) or startup.log |
| `--lines` | no | 200 | Number of trailing lines to show (default: 200) |
| `--follow`, `-f` | no | false | Stream new log lines until interrupted (Ctrl-C) |
| `--since-start` | no | false | Only show lines from the latest successful host start/up marker |

## Human output

Before log lines, the CLI prints a one-line header:

`log=<path> pid=<pid|None> read_at=<iso8601>`

When host discovery has a `start_id` / `start_marker_at` from the latest successful **`host start`** or **`foundry up`**, the default tail (without `--since-start`) is scoped to that start—the same filter as `--since-start`. Lines before the `FOUNDRY_HOST_START start_id=…` marker in `host.log` are omitted. If no marker exists yet, the command shows the trailing `--lines` from the full file.

`--follow` prints the same header, then streams new lines; the initial batch respects the start marker when present.

## See also

- [Operator runbook — observe logs](../operator-runbook.md)
- [`foundry up`](up.md) (writes start markers when it starts the host)
- [Job host status](host-status.md)

## Acceptance

[test_host_logs.py](../../.cursor/foundry/cli/tests/unit/test_host_logs.py)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
