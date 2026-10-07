# Flow node inventory (29 nodes)

Factory flow: [registry.yaml](../../.cursor/foundry/flows/implementation/registry.yaml) (`implementation`). Node contracts: `nodes/{id}/node.yaml`. Catalog indexes: `docs/catalog/implementation/nodes/*.index.yaml` (`foundry catalog build`).

**Verify evidence (shipped):** intake blocks without SHA/branch/diff; acceptance derives `gate_decision` + `evidence_ok` from diff assessment (pass requires explicit `evidence_ok: true`, typically stub override until G1 closes); code quality runs manifest commands off stub. Unit coverage: `tests/unit/test_verify_evidence.py`.

**Instruction ref:** `ok` = resolved on disk under `.cursor/foundry/`; `missing` = declared but no file; `n/a` = no `instructions` asset in catalog (gate may use flow `prompt` only).

**Boundary status:** from [`node_capability.boundary_status`](../../.cursor/foundry/cli/foundry_cli/engine/node_capability.py). The table below covers all 29 flow nodes. [`audit_rows`](../../.cursor/foundry/cli/foundry_cli/engine/node_capability.py) and [execute-verify-boundary-audit.md](execute-verify-boundary-audit.md) list only `execute.start` → `deliver.stub` (workflow-02 Execute/Verify boundary). Shape judgment steps are **implemented** via agent task bindings + `shape_step_executor.py` completers; `boundary_status` registers them explicitly (gap **G10**). Advancement truth for all nodes is [`classify_advance_node`](../../.cursor/foundry/cli/foundry_cli/engine/advance_classifier.py) + dispatch registries in `advance.py`, not `operations.yaml`.

## `operations.yaml` stance (engine-kernel Phase 4, REL-018)

| Stance | Meaning | Runtime |
| --- | --- | --- |
| **A (default)** | `nodes/{id}/operations.yaml` is **authoring / docgen only** unless the flow registry binds an `operations` ref for execution (none on the implementation flow today). | Mechanism truth = flow **checks** (`registry.yaml` `on_open` / `on_seal`), **class handlers** (`advance_classifier` → `intake_executor.py`, `shape_step_executor.py`, `execute_step_executor.py`, `verify_step_executor.py`), and **agent tasks** (`tasks/{id}.yaml`). Docgen may load operations for steward prose via `doc.yaml`. |
| **B (future)** | Typed **mechanism schema** + generic interpreter that executes operations steps from YAML. | **Not implemented.** Do not add a generic operations executor or bind operations for advancement without a charter REL. Phase 2 advance classifier remains the dispatch authority. |

Per-node cleanup plans and generated node docs repeat stance **A** where `operations.yaml` exists (e.g. `shape.intake`, `shape.examine`, execute/verify engine-owned steps). Stance **B** is documented here only as a later kernel option ([engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) Phase 4).

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
| `execute.branch` | step | — | 0 | ok (`nodes/execute.branch/doc.yaml`) | implemented (`GIT_MECHANICAL_STEP` in `advance_classifier.py`) |
| `execute.plan` | step | `execute.plan` task | 2 | ok (`nodes/execute.plan/judgment.md`) | implemented |
| `execute.build` | step | — | 2 | n/a (engine-owned; `nodes/execute.build/doc.yaml`) | implemented |
| `execute.test` | step | — | 2 | n/a (engine-owned; `nodes/execute.test/doc.yaml`) | implemented |
| `execute.test.gate` | gate | engine | 2 | n/a (`nodes/execute.test.gate/doc.yaml`) | gate-engine |
| `execute.repair.limit.gate` | gate | engine | 1 | n/a | gate-engine |
| `execute.commit` | step | — | 2 | n/a (engine-owned; `nodes/execute.commit/doc.yaml`) | implemented |
| `execute.commit.gate` | gate | engine | 3 | n/a | gate-engine |
| `verify.intake` | step | — | 7 | n/a (engine-owned; `nodes/verify.intake/doc.yaml`) | implemented |
| `verify.intake.gate` | gate | engine | 2 | n/a | gate-engine |
| `verify.acceptance` | step | — | 2 | n/a (engine-owned; `nodes/verify.acceptance/doc.yaml`) | implemented (`verify.acceptance` task) |
| `verify.acceptance.gate` | gate | engine | 1 | n/a (`nodes/verify.acceptance.gate/doc.yaml`) | gate-engine |
| `verify.code_quality` | step | — | 3 | n/a (engine-owned; `nodes/verify.code_quality/doc.yaml`) | implemented |
| `verify.code_quality.gate` | gate | engine | 1 | n/a (`nodes/verify.code_quality.gate/doc.yaml`) | gate-engine |
| `verify.code_review` | step | — | 2 | n/a (engine-owned; `nodes/verify.code_review/doc.yaml`) | implemented |
| `verify.code_review.gate` | gate | user | 1 | ok | gate-user |
| `verify.complete` | step | — | 0 | ok (`nodes/verify.complete/doc.yaml`) | implemented |
| `verify.complete.gate` | gate | user | 0 | ok | gate-user |
| `deliver.stub` | step | — | 0 | engine-owned (no step md) | implemented |

## Step instructions (Execute / Verify / Deliver)

No `registry:steps/*` host step files remain on the implementation flow; terminal `deliver.stub` is engine-owned like `verify.complete`. `execute.intake`, `execute.branch`, and `verify.intake` are engine-owned with authoring under `nodes/*/` (legacy step markdown removed for intake nodes).

## Check catalog notes (Step 0 review)

Flow-level command checks requiring implementation (currently stub-pass in hooks except `validate_manifest`):

| Check ID | Used at (examples) | Step 0 owner |
| --- | --- | --- |
| `validate-git-clean-execute` | `execute.intake` on_open | Step 1 hooks |
| `validate-verify-context` | `verify.intake` on_open | Step 1 hooks |
| `ensure-execution-graph-reference` | `execute.plan` on_open | Step 1 hooks |
| `validate-build-exit` | `execute.build` on_seal | Step 1 hooks |

Loop limit checks `repair-within-limit` and `reverify-within-limit` are implemented in `loop_limits.py` (hooks, routing, engine resolvers). Other expression checks (e.g. `review-enabled`) still route through `routing.evaluate_when_expression`.

## Static route gap (decision recorded)

`shape.record.gate` option `hold` routes to `shape.present` (loop `reshape_plan`) per [workflow-02-step0-decisions.md](workflow-02-step0-decisions.md#2-shape-recordgate-declares-hold-without-a-connection).

## Regeneration

Recompute boundary column after engine changes:

```powershell
Set-Location .cursor\foundry\cli
python -c "from pathlib import Path; from foundry_cli.registry import load_registry; from foundry_cli.engine.node_capability import audit_rows; b=Path('..').resolve(); _,f=load_registry(b); print(audit_rows(f,b))"
```

See also [execute-verify-boundary-audit.md](execute-verify-boundary-audit.md).
