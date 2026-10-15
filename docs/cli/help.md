# `help`

Status: **implemented**

Operator help index (same curriculum as foundry -h). Use help -a for all top-level commands and help <command> for subcommand argparse help.

## Invocation

```bash
foundry help [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `-a`, `--all` | no | false | List all top-level commands (listed and unlisted) |
| `help_command` | no | — | Show detailed help for a top-level command |

## Acceptance

[test_foundry_help_command.py](../../.cursor/foundry/cli/tests/unit/test_foundry_help_command.py)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
