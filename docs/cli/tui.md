# `tui`

Status: **implemented**

Interactive Textual UI for the job host: list runs, view context and events, and submit decide/answer/start/advance without low-level visit commands.

## Invocation

```bash
foundry tui [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Open this run id immediately instead of the run list |

## Acceptance

[test_tui.py](../../.cursor/foundry/cli/tests/unit/test_tui.py)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
