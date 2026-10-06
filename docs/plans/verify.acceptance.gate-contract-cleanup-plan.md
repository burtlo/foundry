# Plan: `verify.acceptance.gate` contract cleanup

Status: **done** (this implementer slice).

Related: [workflow node revision patterns](workflow-node-revision-patterns.md), upstream [verify.acceptance contract cleanup](verify.acceptance-contract-cleanup-plan.md), author reference [nodes/verify.acceptance.gate/doc.yaml](../../.cursor/foundry/nodes/verify.acceptance.gate/doc.yaml).

## Goal

`verify.acceptance.gate` is an **engine decider gate with no model worker**: the host admits the visit after sealed `verify.acceptance`, `resolve_engine_gate` reads `verify-findings.json` (`gate_decision`, `evidence_ok` for pass), seals the gate, and routes. The steward does **not** use `gate decide`.

| Layer | Owner |
|-------|--------|
| **Judgment** | **None** — decision is deterministic from sealed findings |
| **Mechanism** | Engine: `_verify_acceptance_gate_decision` in `gates.py` via `run advance` |
| **Policy** | `on_examine` `prior-verify-acceptance-sealed` |
| **Presentation** | Steward markdown `## Acceptance evidence` from `reads.verify_findings` + `reads.acceptance_receipt` |

Happy path:

```
verify.acceptance sealed → admit verify.acceptance.gate → on_examine
  → run advance → resolve_engine_gate (gate_decision pass + evidence_ok) → verify.code_quality
```

**Agent necessity (Step 6):** **A — Fully deterministic engine gate.** No worker, no `instructions.md`.

## Runtime sequence (Step 1)

1. Incoming: `verify.acceptance` **completed** (findings artifact + agent receipt sealed).
2. Visit admitted → `on_examine`: `prior-verify-acceptance-sealed`.
3. Host / `run advance` calls `resolve_engine_gate_decision`.
4. Engine loads latest sealed `verify.acceptance` visit, reads `verify-findings` artifact.
5. Maps `gate_decision` to connection decisions (`pass`, `replan`, `reshape`, `rework_execute`); pass requires `evidence_ok: true`.
6. Seals gate and routes.

Mechanism in `gates.py`; flow node block already `decider: engine`.

## Contract (Step 2)

### Inputs

| When gate opens | Source |
|-----------------|--------|
| Sealed `verify.acceptance` visit | Ledger |
| `verify-findings.json` | `artifact.linked` on acceptance visit |
| Agent receipt (display) | `receipt.linked` on acceptance visit |

### Outputs

| On complete | Output |
|-------------|--------|
| Sealed gate, outcome `completed` | Route per `gate_decision` |
| `gate.resolved` event | Downstream history predicates (`acceptance-passed`) |

### Consumers

| Consumer | Uses |
|----------|------|
| `verify.code_quality` | Incoming on **pass** |
| `execute.plan` / `shape.intake` / `execute.intake` | Loop routes on non-pass decisions |

## Minimal schema (Step 9)

No `instructions`, `worker`, or steward `allow.cli` on the gate node. Context packet exposes `decider: engine` and optional `reads.verify_findings` / `reads.acceptance_receipt` (not in flow `reads` block — assembled in `context.py`).

## Gaps addressed in this slice

| Area | Fix |
|------|-----|
| No steward evidence in context | `verify_acceptance_evidence_for_sealed_step` + context reads |
| No markdown blurb | `render.py` `## Acceptance evidence` |
| No authoring doc | `nodes/verify.acceptance.gate/doc.yaml` + catalog `authoring` |
| Patterns / ownership docs | `workflow-node-revision-patterns.md`, `node-instructions.mdc` |

## Testing

```bash
cd .cursor/foundry/cli
pytest tests/unit/test_verify_evidence.py tests/unit/test_verify_acceptance_gate_context.py -q
pytest tests/unit/test_render.py -q -k "acceptance_gate or verify_acceptance"
pytest tests/unit/test_registry_refs.py -q
```

## Acceptance criteria

| # | Criterion |
|---|-----------|
| AC1 | Opened `verify.acceptance.gate` context has `decider: engine`, no `instructions` |
| AC2 | Context `reads.verify_findings` reflects sealed artifact `gate_decision` / `evidence_ok` |
| AC3 | Context `reads.acceptance_receipt` reflects sealed agent receipt status |
| AC4 | `run context` markdown includes `## Acceptance evidence` and `run advance` (no `gate decide`) |
| AC5 | Catalog index lists `authoring: registry:nodes/verify.acceptance.gate/doc.yaml` |
| AC6 | No `instructions.md` under `nodes/verify.acceptance.gate/` |

## Verification checklist

- [x] `nodes/verify.acceptance.gate/doc.yaml` (no `instructions.md`).
- [x] `gates.py` evidence summary; `context.py` + `render.py`.
- [x] Catalog `authoring` on both index paths.
- [x] `node-instructions.mdc` + patterns doc.
- [x] Unit tests.
