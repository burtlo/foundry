# Flow node inventory (29 nodes)

Factory flow: [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml) (`implementation`). Catalog indexes: `.cursor/foundry/catalog/nodes/*.index.yaml`.

**Baseline (2026-10-06):** Verify evidence hardening — intake blocks without SHA/branch/diff; acceptance derives `gate_decision` + `evidence_ok` from diff assessment; code quality runs manifest commands off stub. See [verify-evidence-hardening-plan.md](verify-evidence-hardening-plan.md).

**Instruction ref:** `ok` = resolved on disk under `.cursor/foundry/`; `missing` = declared but no file; `n/a` = no `instructions` asset in catalog (gate may use flow `prompt` only).

**Boundary status:** from [`node_capability.boundary_status`](../../.cursor/foundry/cli/foundry_cli/engine/node_capability.py). Execute and Verify host steps (`execute.intake` … `deliver.stub`) are **implemented** in `execute_step_executor.py` / `verify_step_executor.py` and advanced from `advance.py`. Shape steps `shape.intake`, `shape.present`, and `shape.record` remain host-advanced with capability label `unsupported` until generic executor registration.

| Node | Kind | Decider | Checks (total) | Instruction ref | Boundary status |
| --- | --- | --- | ---: | --- | --- |
| `shape.intake` | step | — | 3 | ok (`nodes/shape.intake/judgment.md`) | unsupported† |
| `shape.examine` | step | — | 2 | ok (`nodes/shape.examine/judgment.md`) | implemented |
| `shape.examine.gate` | gate | user | 1 | ok | gate-user |
| `shape.present` | step | — | 2 | ok | unsupported† |
| `shape.present.gate` | gate | user | 1 | ok | gate-user |
| `shape.record` | step | — | 3 | ok | unsupported† |
| `shape.record.gate` | gate | user | 2 | ok | gate-user |
| `execute.start` | gate | user | 1 | n/a | gate-user |
| `execute.intake` | step | — | 5 | ok (`steps/execute-intake.md`) | implemented |
| `execute.intake.gate` | gate | engine | 2 | n/a | gate-engine |
| `execute.branch` | step | — | 1 | ok (`steps/execute-branch.md`) | implemented |
| `execute.plan` | step | — | 4 | ok (`steps/execute-plan.md`) | implemented |
| `execute.build` | step | — | 4 | ok (`steps/execute-build.md`) | implemented |
| `execute.test` | step | — | 2 | ok (`steps/execute-test.md`) | implemented |
| `execute.test.gate` | gate | engine | 1 | n/a | gate-engine |
| `execute.repair.limit.gate` | gate | engine | 1 | n/a | gate-engine |
| `execute.commit` | step | — | 3 | ok (`steps/execute-commit.md`) | implemented |
| `execute.commit.gate` | gate | engine | 3 | n/a | gate-engine |
| `verify.intake` | step | — | 6 | ok (`steps/verify-intake.md`) | implemented |
| `verify.intake.gate` | gate | engine | 2 | n/a | gate-engine |
| `verify.acceptance` | step | — | 2 | ok (`steps/verify-acceptance.md`) | implemented |
| `verify.acceptance.gate` | gate | engine | 1 | n/a | gate-engine |
| `verify.code_quality` | step | — | 3 | ok (`steps/verify-code-quality.md`) | implemented |
| `verify.code_quality.gate` | gate | engine | 1 | n/a | gate-engine |
| `verify.code_review` | step | — | 2 | ok (`steps/verify-code-review.md`) | implemented |
| `verify.code_review.gate` | gate | user | 1 | ok | gate-user |
| `verify.complete` | step | — | 1 | ok (`steps/verify-complete.md`) | implemented |
| `verify.complete.gate` | gate | user | 0 | ok | gate-user |
| `deliver.stub` | step | — | 0 | ok (`steps/deliver-stub.md`) | implemented |

† Runtime-advanced today; capability audit label pending Step 1 generic executor registration.

## Step instructions (Execute / Verify / Deliver)

All twelve `registry:steps/*` host step files are present under `.cursor/foundry/steps/` (execute-intake through deliver-stub).

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

`shape.record.gate` option `hold` has no connection in factory-flow; Step 1/Shape polish must add `hold` → `shape.present` per [workflow-02-step0-decisions.md](workflow-02-step0-decisions.md#2-shape-recordgate-declares-hold-without-a-connection).

## Regeneration

Recompute boundary column after engine changes:

```powershell
Set-Location .cursor\foundry\cli
python -c "from pathlib import Path; from foundry_cli.registry import load_registry; from foundry_cli.engine.node_capability import audit_rows; b=Path('..').resolve(); _,f=load_registry(b); print(audit_rows(f,b))"
```

See also [execute-verify-boundary-audit.md](execute-verify-boundary-audit.md).
