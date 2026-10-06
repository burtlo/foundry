# `run archive`

Status: **implemented**

Move a workspace run into the Foundry repo `runs/` store with a sequential archive slug (`{app_id}-NNNN`), preserving the original engine run_id in `archive/manifest.json`. Optionally attach transcript and evaluation review.

## Invocation

```bash
foundry run archive [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id slug under workspace .foundry/runs/ |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--archive-root` | no | — | Override archive directory (default: {foundry_repo}/runs) |
| `--archive-slug` | no | — | Explicit archive folder name (default: next {app_id}-NNNN under archive root) |
| `--transcript` | no | — | Path to steward chat transcript (.jsonl) to copy |
| `--review-file` | no | — | Path to evaluation review markdown to copy |
| `--dry-run` | no | false | Preview archive slug and manifest without moving |
| `--copy` | no | false | Copy the run instead of moving it from the workspace |

## Acceptance

[run_archive.feature](../../.cursor/foundry/cli/tests/acceptance/features/run_archive.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
