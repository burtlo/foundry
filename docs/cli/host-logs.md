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

## Acceptance

[test_host_logs.py](../../.cursor/foundry/cli/tests/unit/test_host_logs.py)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
