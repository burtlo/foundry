# `down`

Status: **implemented**

Stop the judgment bridge and job host that foundry up reconciles for this workspace. Idempotent when already stopped.

## Invocation

```bash
foundry down [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

_No command-specific flags._

## Acceptance

[test_foundry_down.py](../../.cursor/foundry/cli/tests/unit/test_foundry_down.py)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
