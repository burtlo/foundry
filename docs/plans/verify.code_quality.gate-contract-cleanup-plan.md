# Plan: `verify.code_quality.gate` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node revision patterns](workflow-node-revision-patterns.md), upstream [verify.code_quality contract cleanup](verify.code_quality-contract-cleanup-plan.md), author reference [nodes/verify.code_quality.gate/doc.yaml](../../.cursor/foundry/nodes/verify.code_quality.gate/doc.yaml).

## Goal

`verify.code_quality.gate` is an **engine decider gate with no steward worker and no instructions file**: the host or steward uses `run advance` to resolve **pass** or **repair** from the sealed `verify.code_quality` implementation-validator agent receipt (command exit codes and receipt status). Presentation is engine-owned markdown (`## Code quality evidence`).

| Layer | Owner |
|-------|--------|
| **Judgment** | **None** — pass/repair from receipt evidence in `gates.py` |
| **Mechanism** | `resolve_engine_gate` → `_verify_code_quality_gate_decision` |
| **Policy** | `on_examine` `code-quality-done-or-skipped` |
| **Presentation** | `reads.code_quality_receipt` + `render.py` evidence section |

Happy path:

```
verify.code_quality completed → admit verify.code_quality.gate → run advance
  → pass → verify.code_review
```

Repair path:

```
non-zero command exit or failed/partial receipt → repair → execute.repair.limit.gate
```

**Agent necessity (Step 6):** **A — Fully deterministic engine gate.**

## Runtime sequence (Step 1)

1. Incoming: sealed `verify.code_quality` with outcome `completed` (skip path routes to `verify.code_review` without this gate).
2. Visit admitted → `on_examine`: `code-quality-done-or-skipped`.
3. `run advance` calls `resolve_engine_gate` → receipt command exit codes and status.
4. Seal gate, route per decision.

`doc.yaml`: author-only docgen. Mechanism in `gates.py`.

## Contract (Step 2)

### Inputs

| When gate opens | Source |
|-----------------|--------|
| Sealed `verify.code_quality` visit | Ledger `visit.sealed` |
| Agent receipt (`implementation-validator`) | Linked on quality visit |

### Outputs

| On complete | Output |
|-------------|--------|
| Decision `pass` | Route to `verify.code_review` |
| Decision `repair` | Route to `execute.repair.limit.gate` |

### Consumers

| Consumer | Uses |
|----------|------|
| `verify.code_review` | Assumes code quality gate passed or step skipped |
| `execute.repair.limit.gate` | Repair loop after quality failure |

## Minimal schema (Step 9)

Factory-flow already has `decider: engine`, `produces.options: [pass, repair]`, no `instructions`.

## Gaps addressed in this slice

| Area | Fix |
|------|-----|
| No author `doc.yaml` | `nodes/verify.code_quality.gate/doc.yaml` + catalog `authoring` |
| Steward context evidence | `code_quality_receipt_summary_for_sealed_step` + `context.py` reads |
| Presentation | `render.py` `## Code quality evidence` |
| Context packet schema | `reads.code_quality_receipt` (`testReceiptSummary` shape) |
| Ownership docs | `node-instructions.mdc`, `node-inventory.md` |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_verify_evidence.py -q
pytest tests/unit/test_render.py tests/unit/test_verify_code_quality_gate_context.py -q
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | Sealed quality visit with all exit codes 0 → `run advance` resolves **pass** |
| AC2 | Non-zero command exit or failed receipt → **repair** |
| AC3 | Flow has no `instructions` for `verify.code_quality.gate` |
| AC4 | `run context` markdown includes `## Code quality evidence` and no Instructions section |
| AC5 | Context packet validates with `reads.code_quality_receipt` when present |

## Verification checklist

- [x] `factory-flow.yaml` gate block: `decider: engine`, no instructions.
- [x] `nodes/verify.code_quality.gate/doc.yaml`.
- [x] Catalog index `authoring`.
- [x] `gates.py` / `context.py` / `render.py`.
- [x] Unit tests.
