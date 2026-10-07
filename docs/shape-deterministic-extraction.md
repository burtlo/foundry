# Shape intake & examination — deterministic extraction

Status: **as-built** (refactor discovery deliverable; supersedes the removed `docs/plans/shape-instruction-extraction-plan.md` — see git history).

**Intake contract:** `shape.intake` is **complete** — no flow `instructions`, no `judgment.md`; steward behavior is `steward-ux` + CLI (`visit intake complete`, optional `visit state patch`, or `foundry shape`). Tests: `shape_intake.feature`, `test_intake_executor.py`.

This document records the inventory, boundary, primitives, and follow-on recommendations from separating deterministic workflow behavior from agent judgment for `shape.intake` and `shape.examine`.

## Before / after responsibility breakdown

### shape.intake

| Layer | Before | After (contract cleanup) |
|--------|--------|---------------------------|
| **Deterministic (engine)** | Described in steward prose (CLI fences, proceed/blocked branches, ledger assembly) | `intake_executor.run_shape_intake_complete` + flow lifecycle: `on_open` manifest check, `on_close` artifact completeness, `on_seal` receipt checks, **`INTAKE_BLOCKED` transition policy** |
| **Judgment** | Mixed with orchestration in `instructions.md`; later thin `judgment.md` + worker path | **None on the node** — capture `work_prompt` via CLI; optional `app_folder` via `visit state patch` (documented in `steward-ux` and node-instructions) |
| **Operations manifest** | `operations.yaml` bound in flow as executable spec | **Author-only** (`doc.yaml` / docgen); mechanism implemented in `intake_executor.py` — do not treat YAML steps as runtime |
| **Presentation** | “Explain blockers” in step file | `operations.yaml` `presentation.blocked_message` → future CLI/TUI (Slice 6, optional) |
| **Policy** | Steward told not to transition on BLOCKED | Engine denies steward `visit transition` at intake (`CAPABILITY_DENIED`); internal transition only on passed `visit intake complete`; `INTAKE_BLOCKED` when policy invoked on blocked receipt |

### shape.examine

| Layer | Before | After |
|--------|--------|--------|
| **Deterministic** | Seal/transition fences, routing explanation in prose | `operations.yaml` + engine: `prior-shape-intake-sealed`, `agent-receipt-sealed`, routing via `open_clarifying_questions_count` in `flows/implementation/registry.yaml` connections |
| **Judgment** | Full examination conversation in `instructions.md` | `judgment.md`: understand request, ask questions, draft AC, set counters |
| **Presentation** | Implicit in chat | `allow.user.ask` + future CLI attach |
| **Policy** | Steward told fast lane vs gate | Engine connection `when:` expressions only |

## Phase 1 — Instruction inventory (summary)

Full line-level inventory lived in git history for `instructions.md` (removed). Classifications:

### shape.intake (former `instructions.md`)

| Instruction | Class | Agent-facing? | Eventual home (as-built) |
|-------------|-------|---------------|---------------------------|
| Publish ticket / seal receipts (goal) | Mechanism | No | **`visit intake complete`** (`intake_executor.py`) |
| Confirm scope / `app_folder` | Steward product | Yes (when ambiguous) | **steward-ux** + `visit state patch`; engine defaults workspace on complete |
| Launch intake-checker worker | Mechanism | No | **Removed** — legacy agent unbound |
| Do not draft ticket before worker | Policy | No | Engine-only ticket write on passed complete |
| `ledger show` + assemble receipts | Mechanism | No | **`_ledger_checks_for_visit`** in intake executor |
| Proceed: publish, seal, transition | Mechanism | No | Single **`visit intake complete`** command |
| Blocked: seal only, no transition | Policy | No | **Engine** blocked path + **`transition_policy.py`** (`INTAKE_BLOCKED`) |
| “Explain blockers” | Presentation | No | CLI (future `presentation.blocked_message`) |
| Boundaries (no routing, no re-validate manifest) | Policy | No | **`flows/implementation/registry.yaml` `allow.cli`** + capabilities |

### shape.examine (former `instructions.md`)

| Instruction | Class | Agent-facing? | Eventual home |
|-------------|-------|---------------|---------------|
| Read ticket, conduct examination | Judgment | Yes | `judgment.md` |
| `visit state patch` fields | Mechanism | No | `operations.yaml` |
| Build agent receipt, `shape.steward` name | Mechanism (+ Judgment content) | Partial | `operations.yaml` + judgment for conversation summary |
| Patch `open_clarifying_questions_count` before transition | Judgment (value) + Policy (routing) | Yes for count; No for route | Judgment sets count; engine routes |
| Seal + transition | Mechanism | No | `operations.yaml` |
| No worker / no publish artifacts | Policy | No | `flows/implementation/registry.yaml` |

## Phase 2 — Repeated deterministic primitives

| Primitive | Nodes using it | Foundry implementation | Adequate? |
|-----------|----------------|------------------------|-----------|
| Admission checks (`on_open` / `on_examine`) | All steps | `engine/hooks.py` | Yes |
| Artifact completeness on close | Steps with `produces.artifacts` | `artifact_completeness` | Yes |
| Receipt sealed on seal | Intake, examine, … | `on_seal` checks in flow YAML | Yes |
| Ledger `check.recorded` → intake `checks[]` | shape.intake | `intake_executor._ledger_checks_for_visit` | Yes |
| `visit intake complete` | shape.intake | `intake_executor.py` (engine-owned) | Yes |
| `receipt.seal` | shape.examine, … | CLI | Yes (not steward on intake) |
| `visit.transition` | Judgment-bearing steps | CLI + routing | Yes (not on intake steward surface) |
| `agent.invoke` (worker) | shape.intake (legacy) | Legacy / unbound | N/A on happy path |
| Connection routing by state | shape.examine → present / gate | `flows/implementation/registry.yaml` `when:` | Yes |
| Intake blocked → no transition | shape.intake | **`transition_policy.py`** | Yes |
| Context packet assembly | All | `context.py`, `render.py` | Intake: engine note only; examine+: operations + judgment |
| Gate user decide | shape.examine.gate | `gate decide` | Yes (unchanged) |

## Phase 3 — Target execution shape (as-built)

### Intake

```text
enter shape.intake (engine admits, on_open validate-manifest)
    → optional visit state patch (app_folder; default workspace on complete)
    → visit intake complete (engine / foundry.intake — no worker, no node instructions)
    → assemble evidence from ledger checks (intake executor)
    → if passed: publish ticket, seal receipts, transition
    → if blocked: seal blocked intake only; steward cannot transition (capability denied)
    → route to shape.examine on completed + passed intake
```

Legacy **intake-checker.shape** is unbound; stewards must not invoke it on the happy path. See `docs/nodes/shape.intake.md` and **`steward-ux.mdc`**.

### Examination (contract cleanup shipped)

```text
enter shape.examine (on_examine prior-shape-intake-sealed)
    → agent wait → model task shape.examine (judgment.md)
    → run agent submit → engine patches draft_ac, questions, counters
    → [user_input wait + answer if open questions; may supersede and re-dispatch agent]
    → visit examine complete (or run advance when open_clarifying_questions_count == 0)
    → engine seals agent receipt, transition
    → routes to shape.present OR shape.examine.gate (gate path: --with-open-questions)
```

Steward manual `visit state patch` / `receipt seal` / `visit transition` on this node are **denied** by flow capabilities.

## Phase 6 — Unresolved classifications

| Item | Why unclear |
|------|-------------|
| Confirm `app_folder` with user | Product/docs (`steward-ux`) when path ambiguous; mechanism defaults to workspace on complete |
| Receipt `summary_markdown` wording | Judgment (agent prose) vs Presentation (CLI template) |
| Examination conversation in agent receipt | Judgment content, mechanism file write |

(Intake worker → receipt mapping and steward-authored intake JSON are **obsolete** after contract cleanup.)

## Next architectural step (not implemented here)

1. **Generic operations executor** reads `operations.yaml` for nodes that still bind it (optional; intake does not).
2. **Register operations** on remaining shape/execute/verify step nodes until executor lands.
3. **Cursor SDK** for `agent.invoke` steps only (examine task, etc.).
4. **CLI presentation** layer for `presentation.*` blocks (intake `blocked_message`, gate prompts).

## Verification

- Unit: `test_intake_executor.py`, `test_shape_examine_complete.py`, `test_transition_policy.py`, `test_advance.py`, `test_engine.py` (capability denials), `test_render.py`
- Acceptance: `shape_intake.feature`, `shape_examine.feature`, `shape_phase_e2e.feature`, `run_context.feature`, `catalog_build.feature`
- Contract: `flows/implementation/registry.yaml` `shape.intake` + `shape.examine` nodes + `@node.shape.intake` / `@node.shape.examine` features

## Runtime artifacts

| Path | Role |
|------|------|
| `nodes/shape.intake/doc.yaml` | Author sequence + ownership (docgen) |
| `nodes/shape.intake/operations.yaml` | Author-only mechanism narrative (not flow-bound) |
| `nodes/shape.examine/operations.yaml` | Author-only mechanism narrative (not flow-bound) |
| `nodes/shape.examine/judgment.md` | Agent judgment (flow-bound as `instructions`) |
| `cli/foundry_cli/engine/intake_executor.py` | Intake mechanism |
| `cli/foundry_cli/engine/transition_policy.py` | Enforced intake blocked policy |
| `cli/foundry_cli/node_operations.py` | Loader for operations manifests |

Context markdown at **shape.intake**: short engine note (no `## Judgment`). At **shape.examine**: engine completion note plus **Judgment** (operations are author-only, not flow-bound).
