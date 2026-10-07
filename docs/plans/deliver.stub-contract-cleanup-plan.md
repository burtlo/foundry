# Plan: `deliver.stub` contract cleanup

Status: **done** (implementer slice; uncommitted).

Related: [verify.complete.gate contract cleanup](verify.complete.gate-contract-cleanup-plan.md), [workflow-02 step0 decisions](workflow-02-step0-decisions.md) §11.

## Goal

`deliver.stub` is the **workflow terminal**: no steward step file, no worker. The engine patches `deliver_handoff_message`, seals the visit, and marks the run `completed` on **`run advance`** when the visit is `opened` (`run_deliver_stub_complete` in `advance.py`).

| Layer | Owner |
|-------|--------|
| **Judgment** | None |
| **Mechanism** | Engine: `run_deliver_stub_complete` via `run advance` |
| **Policy** | `terminal: true`; admission after `verify.complete.gate` **accept** |
| **Presentation** | Engine-owned markdown blurb in `render.py` (`## Deliver (terminal)`) |

## Runtime sequence

1. Incoming: sealed `verify.complete.gate` with decision **accept**.
2. Visit admitted → `deliver.stub` opened.
3. Host / steward `run advance` → handoff message in state → visit sealed → run `completed`.

## Contract

### Inputs

Handoff fields already in run state from verify/execute (`feature_branch`, `final_commit_sha`); no `reads` block on the node.

### Outputs

| State patch | Exposure |
|-------------|----------|
| `deliver_handoff_message` | `get_run` / `run status` → `handoff_message` |

No artifacts or receipts.

## Instruction audit

| Asset | Action |
|-------|--------|
| `registry:steps/deliver-stub.md` | **REMOVE** — engine-only; no `instructions` in `flows/implementation/registry.yaml` |
| `node-instructions.mdc` | **ADD** Deliver stub engine-owned row |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_deliver_stub_context.py -q
pytest tests/unit/test_registry_refs.py -q
pytest tests/unit/test_render.py -q -k "deliver_stub"  # optional if render cases added
pytest tests/unit/test_workflow_slices_2c_2f.py::test_full_path_reaches_deliver_stub_with_handoff -q
```

### Schema oracle

| Element | Prove |
|---------|--------|
| No `instructions` in flow node | `assemble_context` omits `instructions` |
| `terminal: true` | Catalog index + `build_node_index` |
| Markdown | `## Deliver (terminal)` + `run advance`; no `## Instructions` |
| Advance | Slice 2F integration sets `deliver_handoff_message` and `status == completed` |

Optional later: focused unit test calling `run_deliver_stub_complete` / `advance_run` on a minimal snapshot (mirror `test_advance` style for other engine steps).

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | `flows/implementation/registry.yaml` `deliver.stub` has no `instructions`; `allow.state` includes `deliver_handoff_message` |
| AC2 | `deliver-stub.md` removed; no remaining `registry:steps/deliver-stub.md` refs in implementation flow |
| AC3 | Steward markdown context is engine blurb only |
| AC4 | Unit context + registry ref tests pass; slice 2F handoff test passes |

## Verification checklist

- [x] `flows/implementation/registry.yaml` deliver.stub block engine-owned.
- [x] Catalog index YAML: no `assets.instructions`.
- [x] `node-instructions.mdc` Deliver stub row.
- [x] `render.py` terminal blurb.
- [x] `test_deliver_stub_context.py` + `test_registry_refs.py` updates.
