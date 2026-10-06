# Workflow-02 baseline

Captured at Step 0 of [workflow-02-delivery-plan.md](workflow-02-delivery-plan.md). No tree reset; preexisting changes preserved.

## Revision and date

| Field | Value |
| --- | --- |
| Git `HEAD` | `3d4f0fabbe9d8ac07495dd9638f3aae81ed28567` |
| Short subject | `docs(engine): explicit Execute/Verify unsupported boundaries (step 4)` |
| Baseline date | 2026-10-06 |

## Working tree (at capture)

No staged or modified tracked files at capture time. Local `.foundry/runs/*` artifacts may exist from manual runs; they are not part of this baseline commit.

## Plan files (under `docs/plans/`)

At capture, orchestration sources lived at repo root and were later consolidated:

- [workflow-02-delivery-plan.md](workflow-02-delivery-plan.md) — workflow-02 mission, blockers, Steps 0–2, slice table
- [implementation-review-remediation.md](implementation-review-remediation.md) — F1–F9 findings and ordered remediation (review at `4d2c575`)

## Test commands

Run from repository root with system `python` and `.cursor/foundry/cli/foundry.py` (no repo `.venv` on this machine).

| Command | Exit | Result |
| --- | ---: | --- |
| `python .cursor/foundry/cli/foundry.py dev unit --quiet` | 0 | `suite=unit ok=true` |
| `python .cursor/foundry/cli/foundry.py dev acceptance --quiet` | 0 | `suite=acceptance ok=true` |

Full pytest (same suites the `dev` commands invoke):

```powershell
python -m pytest .cursor/foundry/cli/tests/unit .cursor/foundry/cli/tests/acceptance -q
```

| Result | Detail |
| --- | --- |
| Exit | 0 |
| Passed | **293** |
| Skipped | 5 |
| Duration | ~269s |

## Generated documentation diff

Not run for this baseline snapshot. Slice exit and final acceptance require:

```powershell
python .cursor/foundry/cli/foundry.py dev docs
git diff -- docs .cursor/foundry
```

## Related baseline artifacts

- [Execute / Verify boundary audit](execute-verify-boundary-audit.md) — host behavior at `3d4f0fa` for `execute.start` … `deliver.stub`
- [Node inventory](node-inventory.md) — all 29 flow nodes
- [Step 0 decisions](workflow-02-step0-decisions.md) — contract choices before Step 1 code

## Recent prerequisite commits (context)

| Commit | Scope |
| --- | --- |
| `ad9eb8a` | Remediation step 1 — host sockets, ownership |
| `15e1fe9` | Remediation step 2 — durable dispatch, ledger checkpoints, idempotency digests |
| `c45e713` | Remediation step 3 — host-owned Shape steps, re-examination, verbatim input |
| `3d4f0fa` | Remediation step 4 — Execute/Verify unsupported boundaries in engine |
