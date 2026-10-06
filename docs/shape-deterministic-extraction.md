# Shape intake & examination — deterministic extraction

Status: **as-built** (refactor discovery deliverable)

This document records the inventory, boundary, primitives, and follow-on recommendations from separating deterministic workflow behavior from agent judgment for `shape.intake` and `shape.examine`.

## Before / after responsibility breakdown

### shape.intake

| Layer | Before | After |
|--------|--------|--------|
| **Deterministic (engine + operations.yaml)** | Described in steward prose (CLI fences, proceed/blocked branches, ledger assembly) | `operations.yaml` + engine: `on_open` manifest check, `on_close` artifact completeness, `on_seal` receipt checks, **`INTAKE_BLOCKED` transition policy** |
| **Judgment (judgment.md + worker)** | Mixed with orchestration in `instructions.md` | Worker: PROCEED/BLOCKED, ticket proposal, assessment markdown; steward: confirm `app_folder` when ambiguous |
| **Presentation** | “Explain blockers” in step file | `operations.yaml` `presentation.blocked_message` → future CLI/TUI |
| **Policy** | Steward told not to transition on BLOCKED | Engine rejects `visit transition` when sealed intake receipt `status == blocked` |

### shape.examine

| Layer | Before | After |
|--------|--------|--------|
| **Deterministic** | Seal/transition fences, routing explanation in prose | `operations.yaml` + engine: `prior-shape-intake-sealed`, `agent-receipt-sealed`, routing via `open_clarifying_questions_count` in `factory-flow.yaml` connections |
| **Judgment** | Full examination conversation in `instructions.md` | `judgment.md`: understand request, ask questions, draft AC, set counters |
| **Presentation** | Implicit in chat | `allow.user.ask` + future CLI attach |
| **Policy** | Steward told fast lane vs gate | Engine connection `when:` expressions only |

## Phase 1 — Instruction inventory (summary)

Full line-level inventory lived in git history for `instructions.md` (removed). Classifications:

### shape.intake (former `instructions.md`)

| Instruction | Class | Agent-facing? | Eventual home |
|-------------|-------|---------------|---------------|
| Publish ticket / seal receipts (goal) | Policy + Mechanism | No | `factory-flow.yaml` lifecycle + `operations.yaml` |
| Confirm scope / `app_folder` | Judgment (+ Mechanism patch) | Yes (confirm path) | `judgment.md`; default patch in `operations.yaml` |
| Launch intake-checker worker | Mechanism | No | `operations.yaml` `agent.invoke` |
| Do not draft ticket before worker | Policy | No | Worker contract + engine artifact rules |
| `ledger show` + assemble receipts | Mechanism | No | `operations.yaml` |
| Proceed: publish, seal, transition | Mechanism | No | `operations.yaml` |
| Blocked: seal only, no transition | Policy | No | **Engine `INTAKE_BLOCKED`** + `operations.yaml` |
| “Explain blockers” | Presentation | No | CLI |
| Boundaries (no routing, no re-validate manifest) | Policy | No | Engine capabilities + hooks |

### shape.examine (former `instructions.md`)

| Instruction | Class | Agent-facing? | Eventual home |
|-------------|-------|---------------|---------------|
| Read ticket, conduct examination | Judgment | Yes | `judgment.md` |
| `visit state patch` fields | Mechanism | No | `operations.yaml` |
| Build agent receipt, `shape.steward` name | Mechanism (+ Judgment content) | Partial | `operations.yaml` + judgment for conversation summary |
| Patch `open_clarifying_questions_count` before transition | Judgment (value) + Policy (routing) | Yes for count; No for route | Judgment sets count; engine routes |
| Seal + transition | Mechanism | No | `operations.yaml` |
| No worker / no publish artifacts | Policy | No | `factory-flow.yaml` |

## Phase 2 — Repeated deterministic primitives

| Primitive | Nodes using it | Foundry implementation | Adequate? |
|-----------|----------------|------------------------|-----------|
| Admission checks (`on_open` / `on_examine`) | All steps | `engine/hooks.py` | Yes |
| Artifact completeness on close | Steps with `produces.artifacts` | `artifact_completeness` | Yes |
| Receipt sealed on seal | Intake, examine, … | `on_seal` checks in flow YAML | Yes |
| Ledger `check.recorded` → intake `checks[]` | shape.intake | Steward assembly today | Partial — executor should assemble |
| `artifact.publish` | shape.intake | CLI | Yes |
| `receipt.seal` | shape.intake, shape.examine | CLI | Yes |
| `visit.transition` | Steps | CLI + routing | Yes |
| `agent.invoke` (worker) | shape.intake | Task / future SDK | Partial |
| Connection routing by state | shape.examine → present / gate | `factory-flow.yaml` `when:` | Yes |
| Intake blocked → no transition | shape.intake | **`transition_policy.py`** | Yes (new) |
| Context packet assembly | All | `context.py`, `render.py` | Extended with **operations** |
| Gate user decide | shape.examine.gate | `gate decide` | Yes (unchanged) |

## Phase 3 — Target execution shape (as-built)

### Intake

```
enter shape.intake (engine admits, on_open validate-manifest)
    → optional app_folder patch (default workspace)
    → visit intake complete (engine / foundry.intake — no worker on happy path)
    → assemble evidence from ledger checks (intake executor)
    → if passed: publish ticket, seal receipts, transition
    → if blocked: seal blocked intake only; engine denies transition (INTAKE_BLOCKED)
    → route to shape.examine on completed + passed intake
```

Legacy **intake-checker.shape** is unbound in Phase 1; stewards must not invoke it on the happy path (see `judgment.md` and `operations.yaml`).

### Examination

```
enter shape.examine (on_examine prior-shape-intake-sealed)
    → steward examination conversation (judgment)
    → patch draft_ac + open_clarifying_questions_count
    → seal agent receipt, transition
    → engine routes to shape.present OR shape.examine.gate
```

## Phase 6 — Unresolved classifications

| Item | Why unclear |
|------|-------------|
| Confirm `app_folder` with user | Judgment when path ambiguous; mechanism when defaulting to workspace |
| Receipt `summary_markdown` wording | Judgment (agent prose) vs Presentation (CLI template) |
| Mapping worker PROCEED/BLOCKED → intake receipt `status` | Mechanism (fixed mapping) but currently steward-authored JSON |
| Examination conversation in agent receipt | Judgment content, mechanism file write |

## Next architectural step (not implemented here)

1. **Executor** reads `operations.yaml` and runs `mechanism` steps without an LLM.
2. **Register operations** on remaining shape/execute/verify step nodes (optional until executor lands).
3. **Assemble intake receipt `checks[]` in code** from `ledger show` output.
4. **Cursor SDK** for `agent.invoke` steps only.
5. **CLI presentation** layer for `presentation.*` blocks and gate prompts already in flow YAML.

## Verification

- Unit: `test_transition_policy.py`, `test_node_operations.py`, `test_render.py`
- Acceptance: `shape_intake.feature` (includes `INTAKE_BLOCKED`), `shape_examine.feature`, `run_context.feature`

## Runtime artifacts

| Path | Role |
|------|------|
| `nodes/shape.intake/operations.yaml` | Deterministic spec |
| `nodes/shape.intake/judgment.md` | Agent judgment |
| `nodes/shape.examine/operations.yaml` | Deterministic spec |
| `nodes/shape.examine/judgment.md` | Agent judgment |
| `cli/foundry_cli/engine/transition_policy.py` | Enforced intake blocked policy |
| `cli/foundry_cli/node_operations.py` | Loader for operations manifests |

Context markdown packet sections: **Operations** (YAML, executor-facing) then **Judgment** (agent-facing).
