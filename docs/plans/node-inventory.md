# Flow node inventory (29 nodes)

Factory flow: [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml) (`implementation`). Catalog indexes: `.cursor/foundry/catalog/nodes/*.index.yaml`.

**Verify evidence (shipped):** intake blocks without SHA/branch/diff; acceptance derives `gate_decision` + `evidence_ok` from diff assessment (pass requires explicit `evidence_ok: true`, typically stub override until G1 closes); code quality runs manifest commands off stub. Unit coverage: `tests/unit/test_verify_evidence.py`.

**Instruction ref:** `ok` = resolved on disk under `.cursor/foundry/`; `missing` = declared but no file; `n/a` = no `instructions` asset in catalog (gate may use flow `prompt` only).

**Boundary status:** from [`node_capability.boundary_status`](../../.cursor/foundry/cli/foundry_cli/engine/node_capability.py). Execute and Verify host steps (`execute.intake` … `deliver.stub`) are **implemented** in `execute_step_executor.py` / `verify_step_executor.py` and advanced from `advance.py`. `shape.intake` is **implemented** via `intake_executor.py`. `shape.examine` and `shape.present` are **implemented** via agent submit + `run_shape_examine_complete` / `run_shape_present_complete` (`shape_step_executor.py`). `shape.record` remains host-advanced with capability label `unsupported` until generic executor registration.

| Node | Kind | Decider | Checks (total) | Instruction ref | Boundary status |
| --- | --- | --- | ---: | --- | --- |
| `shape.intake` | step | — | 3 | n/a (engine-owned; no judgment file) | implemented |
| `shape.examine` | step | — | 2 | ok (`nodes/shape.examine/judgment.md`) | implemented |
| `shape.examine.gate` | gate | user | 1 | ok | gate-user |
| `shape.present` | step | — | 2 | ok (`nodes/shape.present/judgment.md`) | implemented |
| `shape.present.gate` | gate | user | 1 | ok (`nodes/shape.present.gate/instructions.md`) | gate-user (context packet inlines `## Plan presentation`) |
| `shape.record` | step | — | 3 | ok | implemented |
| `shape.record.gate` | gate | user | 2 | ok | gate-user (context packet inlines `## Living plan`) |
| `execute.start` | gate | user | 1 | n/a | gate-user |
| `execute.intake` | step | — | 5 | n/a (engine-owned; `nodes/execute.intake/doc.yaml` authoring) | implemented |
| `execute.intake.gate` | gate | engine | 2 | n/a | gate-engine |
| `execute.branch` | step | — | 0 | ok (`nodes/execute.branch/doc.yaml`) | engine-owned |
| `execute.plan` | step | `execute.plan` task | 2 | ok (`nodes/execute.plan/judgment.md`) | implemented |
| `execute.build` | step | — | 2 | n/a (engine-owned; `nodes/execute.build/doc.yaml`) | engine-owned |
| `execute.test` | step | — | 2 | n/a (engine-owned; `nodes/execute.test/doc.yaml`) | engine-owned |
| `execute.test.gate` | gate | engine | 2 | n/a (`nodes/execute.test.gate/doc.yaml`) | gate-engine |
| `execute.repair.limit.gate` | gate | engine | 1 | n/a | gate-engine |
| `execute.commit` | step | — | 2 | n/a (engine-owned; `nodes/execute.commit/doc.yaml`) | engine-owned |
| `execute.commit.gate` | gate | engine | 3 | n/a | gate-engine |
| `verify.intake` | step | — | 7 | n/a (engine-owned; `nodes/verify.intake/doc.yaml`) | implemented |
| `verify.intake.gate` | gate | engine | 2 | n/a | gate-engine |
| `verify.acceptance` | step | — | 2 | n/a (engine-owned; `nodes/verify.acceptance/doc.yaml`) | engine-owned |
| `verify.acceptance.gate` | gate | engine | 1 | n/a (`nodes/verify.acceptance.gate/doc.yaml`) | gate-engine |
| `verify.code_quality` | step | — | 3 | n/a (engine-owned; `nodes/verify.code_quality/doc.yaml`) | engine-owned |
| `verify.code_quality.gate` | gate | engine | 1 | n/a (`nodes/verify.code_quality.gate/doc.yaml`) | gate-engine |
| `verify.code_review` | step | — | 2 | n/a (engine-owned; `nodes/verify.code_review/doc.yaml`) | engine-owned |
| `verify.code_review.gate` | gate | user | 1 | ok | gate-user |
| `verify.complete` | step | — | 1 | ok (`steps/verify-complete.md`) | implemented |
| `verify.complete.gate` | gate | user | 0 | ok | gate-user |
| `deliver.stub` | step | — | 0 | ok (`steps/deliver-stub.md`) | implemented |

† Runtime-advanced today; capability audit label pending Step 1 generic executor registration.

## Step instructions (Execute / Verify / Deliver)

Eight `registry:steps/*` host step files remain under `.cursor/foundry/steps/` (verify-acceptance through deliver-stub). `execute.intake`, `execute.branch`, and `verify.intake` are engine-owned with authoring under `nodes/*/` (legacy step markdown removed for intake nodes).

## Check catalog notes (Step 0 review)

Flow-level command checks requiring implementation (currently stub-pass in hooks except `validate_manifest`):

| Check ID | Used at (examples) | Step 0 owner |
| --- | --- | --- |
| `validate-git-clean-execute` | `execute.intake` on_open | Step 1 hooks |
| `validate-verify-context` | `verify.intake` on_open | Step 1 hooks |
| `ensure-execution-graph-reference` | `execute.plan` on_open | Step 1 hooks |
| `validate-build-exit` | `execute.build` on_seal | Step 1 hooks |

Expression and history checks (e.g. `repair-within-limit`, `reverify-within-limit`, `review-enabled`) depend on Step 1 routing and resolver work.

## Static route gap (decision recorded)

`shape.record.gate` option `hold` routes to `shape.present` (loop `reshape_plan`) per [workflow-02-step0-decisions.md](workflow-02-step0-decisions.md#2-shape-recordgate-declares-hold-without-a-connection).

## Regeneration

Recompute boundary column after engine changes:

```powershell
Set-Location .cursor\foundry\cli
python -c "from pathlib import Path; from foundry_cli.registry import load_registry; from foundry_cli.engine.node_capability import audit_rows; b=Path('..').resolve(); _,f=load_registry(b); print(audit_rows(f,b))"
```

See also [execute-verify-boundary-audit.md](execute-verify-boundary-audit.md).
