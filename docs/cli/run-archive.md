# `run archive`

Status: **implemented**

Move a completed workspace run into the Foundry repository `runs/` store. Assigns a **sequential archive slug** (`{app_id}-NNNN`) independent of the engine `run_id`, so multiple archives of `porcelain-0001` become `porcelain-0002`, `porcelain-0003`, and so on.

## Invocation

```bash
foundry run archive --run "{run_id}" [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | one of `--run` / `--run-dir` | — | Run id under `workspace/.foundry/runs/` |
| `--run-dir` | one of `--run` / `--run-dir` | — | Explicit run directory containing `snapshot.json` |
| `--archive-root` | no | `{foundry_repo}/runs` | Override archive destination directory |
| `--archive-slug` | no | next `{app_id}-NNNN` | Explicit archive folder name |
| `--transcript` | no | — | Steward chat transcript (`.jsonl`) copied to `archive/transcript.jsonl` |
| `--review-file` | no | — | Evaluation review markdown copied to `archive/review.md` |
| `--dry-run` | no | false | Preview slug and manifest without moving |
| `--copy` | no | false | Copy instead of move (leave workspace run in place) |

## Archive layout

```
foundry/runs/porcelain-0002/
  snapshot.json
  artifacts/
  receipts/
  ticket.json
  archive/
    manifest.json      # provenance: run_id, archive_slug, commits, visits
    transcript.jsonl   # when --transcript provided
    review.md          # when --review-file provided
    workspace-plan.md  # copy of workspace plan.md when present
```

`manifest.json` preserves the original engine `run_id` while `archive_slug` is the folder name under `runs/`.

## Acceptance

[run_archive.feature](../../.cursor/foundry/cli/tests/acceptance/features/run_archive.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py) — `cmd_run_archive`
