# Job host delivery (Phases 0–7)

Status: **delivered** (October 2026). Canonical summary of the job-host program (Phases 0–7).

**Architecture (normative):** [concepts/job-host-architecture.md](concepts/job-host-architecture.md)

**Shape intake/examine boundary (as-built):** [shape-deterministic-extraction.md](shape-deterministic-extraction.md)

**Active workflow work:** [plans/shape-execute-verify-gap-closure-plan.md](plans/shape-execute-verify-gap-closure-plan.md), [plans/node-inventory.md](plans/node-inventory.md), per-node plans under [plans/](plans/README.md).

## What shipped

| Phase | Summary | Primary code / docs |
|------|---------|---------------------|
| **0** | Responsibility inventory for Shape nodes | Superseded by [node-inventory](plans/node-inventory.md) + generated [nodes/](nodes/) |
| **1** | Deterministic `shape.intake` (`visit intake complete`); examine judgment split | `intake_executor.py`, [shape-deterministic-extraction.md](shape-deterministic-extraction.md) |
| **2** | Durable `run advance` / `run recover`, revision, `run.wait` | `advance.py`, `run_store` |
| **3** | Persistent local host (socket, `host start` / `host run`) | `foundry_cli/host` |
| **4** | Agent adapter + `shape.examine` task binding | `tasks/shape.examine.yaml`, agent requests on snapshot |
| **5** | User CLI: `shape`, `runs`, `status`, `attach`, `decide`, `answer` | `shape_cli.py`, host protocol |
| **6** | Execute entry: `start`, `retry`, `cancel` | Skeleton complete; full graph automation in gap plan |
| **7** | Append-only `ledger.jsonl` before snapshot commit | `ledger_store`, `storage_version: 2` |

## Still open (not phase blockers)

From the architecture doc and gap plan:

- Full materialized-state replay from events only
- Production HTTP agent adapter without stub auto-accept
- TUI / web UI
- Generic `operations.yaml` executor for all nodes
- Shape → Verify → `deliver.stub` gap items **G1–G10** ([gap closure plan](plans/shape-execute-verify-gap-closure-plan.md))

## Verification (smoke)

From `.cursor/foundry/cli`:

```text
python -m pytest tests/unit/test_advance.py tests/unit/test_run_store_durable.py tests/unit/test_intake_executor.py -q
python -m pytest tests/unit/test_host_protocol.py tests/unit/test_shape_cli.py tests/unit/test_execute_cli.py -q
python -m pytest tests/acceptance/test_shape_intake.py tests/acceptance/test_shape_phase_e2e.py -q
```

Use `foundry dev unit` and `foundry dev acceptance` for CI-equivalent runs.
