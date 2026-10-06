# Flow node inventory (29 nodes)

Factory flow: [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml) (`implementation`). Catalog indexes: `.cursor/foundry/catalog/nodes/*.index.yaml`.

**Instruction ref:** `ok` = resolved on disk under `.cursor/foundry/`; `missing` = declared but no file; `n/a` = no `instructions` asset in catalog (gate may use flow `prompt` only).

**Boundary status:** from [`node_capability.boundary_status`](../../.cursor/foundry/cli/foundry_cli/engine/node_capability.py) at baseline `3d4f0fa`. Shape steps `shape.intake`, `shape.present`, and `shape.record` are **host-advanced** in `advance.py` / dedicated executors even though capability reports `unsupported` until the generic executor registers them.

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
| `execute.intake` | step | — | 5 | **missing** (`steps/execute-intake.md`) | unsupported |
| `execute.intake.gate` | gate | engine | 2 | n/a | gate-engine |
| `execute.branch` | step | — | 1 | **missing** | unsupported |
| `execute.plan` | step | — | 4 | **missing** | unsupported |
| `execute.build` | step | — | 4 | **missing** | unsupported |
| `execute.test` | step | — | 2 | **missing** | unsupported |
| `execute.test.gate` | gate | engine | 1 | n/a | gate-engine |
| `execute.repair.limit.gate` | gate | engine | 1 | n/a | gate-engine |
| `execute.commit` | step | — | 3 | **missing** | unsupported |
| `execute.commit.gate` | gate | engine | 3 | n/a | gate-engine |
| `verify.intake` | step | — | 6 | **missing** | unsupported |
| `verify.intake.gate` | gate | engine | 2 | n/a | gate-engine |
| `verify.acceptance` | step | — | 2 | **missing** | unsupported |
| `verify.acceptance.gate` | gate | engine | 1 | n/a | gate-engine |
| `verify.code_quality` | step | — | 3 | **missing** | unsupported |
| `verify.code_quality.gate` | gate | engine | 1 | n/a | gate-engine |
| `verify.code_review` | step | — | 2 | **missing** | unsupported |
| `verify.code_review.gate` | gate | user | 1 | ok | gate-user |
| `verify.complete` | step | — | 1 | **missing** | unsupported |
| `verify.complete.gate` | gate | user | 0 | ok | gate-user |
| `deliver.stub` | step | — | 0 | **missing** | unsupported |

† Runtime-advanced today; capability audit label pending Step 1 generic executor registration.

## Missing step instructions (blocking for Execute/Verify)

These twelve `registry:steps/*` files are not present under `.cursor/foundry/steps/`:

1. `execute-intake.md`
2. `execute-branch.md`
3. `execute-plan.md`
4. `execute-build.md`
5. `execute-test.md`
6. `execute-commit.md`
7. `verify-intake.md`
8. `verify-acceptance.md`
9. `verify-code-quality.md`
10. `verify-code-review.md`
11. `verify-complete.md`
12. `deliver-stub.md`

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
