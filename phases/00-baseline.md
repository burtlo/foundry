# Phase 0 — Baseline and responsibility inventory

Status: **complete** (inventory only; no job-host or executor implementation).

Related design and delivery:

- [job-host architecture](../docs/concepts/job-host-architecture.md)
- [Phase delivery index](README.md)
- [Shape intake & examination — deterministic extraction](../docs/shape-deterministic-extraction.md) (detailed intake/examine split; referenced here, not duplicated)

## Scope

All seven Shape nodes in flow `implementation` (`factory-flow.yaml` entry `shape.intake`):

| Node | Kind |
|------|------|
| `shape.intake` | step |
| `shape.examine` | step |
| `shape.examine.gate` | gate |
| `shape.present` | step |
| `shape.present.gate` | gate |
| `shape.record` | step |
| `shape.record.gate` | gate |

(`execute.start` follows Shape but is out of this inventory.)

## Cross-cutting as-built behavior

- **Workflow authority:** `.cursor/foundry/flows/factory-flow.yaml` (checks, connections, `reads` / `allow`, lifecycle hooks, workers).
- **Catalog indexes:** `.cursor/foundry/catalog/nodes/*.index.yaml` mirror flow assets, connections, checks, and test paths.
- **Execution today:** Stewards load `run context --markdown`, then invoke allowed CLI commands per step/judgment instructions. The engine evaluates hooks, enforces `transition_policy` (e.g. `INTAKE_BLOCKED`), and selects connections. There is **no** `operations.yaml` executor or `advance()` loop yet.
- **Instruction assets:** Split nodes (`shape.intake`, `shape.examine`) use `judgment.md` (bound as `instructions` in flow) plus `operations.yaml`. Other Shape steps use `instructions.md`. Legacy `shape.intake/instructions.md` and `shape.examine/instructions.md` are **removed**; flow and catalog bind `judgment.md` only.
- **Acceptance fixture debt:** Some steward scenarios under `cli/tests/acceptance` still seal receipts with `intake-checker.shape` agent names for blocked/legacy intake paths. The happy path uses `visit intake complete` instead; fixtures are not rewritten wholesale until a scenario is migrated explicitly.

---

## `shape.intake`

### Authoritative assets

| Asset | Registry ref |
|-------|----------------|
| Judgment | `registry:nodes/shape.intake/judgment.md` |
| Operations (spec) | `registry:nodes/shape.intake/operations.yaml` |
| Worker | `registry:agents/intake-checker.shape.md` + `registry:workers/intake-checker.shape/contract.yaml` |
| Flow node | `factory-flow.yaml` → `shape.intake` |

### Checks and connections

| Hook | Checks |
|------|--------|
| `on_open` | `validate-manifest` |
| `on_seal` | `intake-receipt-sealed`, `agent-receipt-sealed` (reopen on fail) |

**Produces:** artifact `ticket` (`registry:schemas/ticket.schema.json`).

**Out:** `shape.intake-to-shape.examine` on visit outcome `completed`.

**In (loops):** `verify.acceptance.gate` / `verify.code_review.gate` reshape → `shape.intake`.

### Responsibility ownership

| Responsibility | Layer | Owner |
|----------------|-------|-------|
| Node definition, lifecycle checks, connection to examine | Policy | registry |
| `validate-manifest` on open | Mechanism | engine |
| Seal-time receipt checks, artifact completeness on close | Policy | engine |
| Deny `visit transition` when intake receipt `status == blocked` (`INTAKE_BLOCKED`) | Policy | engine |
| Default `app_folder` to workspace when unset | Mechanism | engine (specified in operations; steward may patch first) |
| PROCEED/BLOCKED verdict, ticket field proposal, assessment body | Judgment | worker (`intake-checker.shape`) |
| Confirm `app_folder` with user when ambiguous | Judgment | steward |
| Assemble intake/agent receipts, `ledger show`, publish ticket, seal, transition | Mechanism | steward (CLI today; future executor) |
| Blocked intake messaging template | Presentation | cli (`operations.yaml` `presentation.blocked_message`) |
| Context packet (reads, allow, inlined judgment + operations) | Presentation | cli |

### Test matrix

| Test | What it proves |
|------|----------------|
| `acceptance/features/shape_intake.feature` | Happy path CLI sequence; `INTAKE_BLOCKED`; close without ticket |
| `acceptance/features/run_context.feature` | Context binds `judgment.md` + `operations.yaml`, allow grants |
| `acceptance/features/shape_phase_e2e.feature` | Intake → examine in full Shape slice |
| `acceptance/features/catalog_build.feature` | Catalog index assets and connections |
| `acceptance/features/doc_build.feature`, `dev_commands.feature` | Doc generation smoke |
| `unit/test_transition_policy.py` | Engine blocks/allows intake transition from receipt status |
| `unit/test_node_operations.py` | `operations.yaml` loads; key mechanism ids |
| `unit/test_render.py`, `unit/test_paths.py`, `unit/test_foundry.py` | Context render and registry path resolution |

---

## `shape.examine`

### Authoritative assets

| Asset | Registry ref |
|-------|----------------|
| Judgment | `registry:nodes/shape.examine/judgment.md` |
| Operations (spec) | `registry:nodes/shape.examine/operations.yaml` |
| Worker | None (steward-only judgment; `agent.name` **shape.steward** on receipt) |
| Flow node | `factory-flow.yaml` → `shape.examine` |

### Checks and connections

| Hook | Checks |
|------|--------|
| `on_examine` | `prior-shape-intake-sealed` |
| `on_seal` | `agent-receipt-sealed` (reopen on fail) |

**Reads:** ticket artifact from nearest sealed `shape.intake`; state for examination fields; `config.foundry.shape`.

**Out (engine `when:` on connections):**

- `shape.examine-to-shape.present` when `state.open_clarifying_questions_count == 0`
- `shape.examine-to-shape.examine.gate` when count `!= 0`

**In:** from intake; `shape.examine.gate` reject; `shape.present.gate` reject (refine loop).

### Responsibility ownership

| Responsibility | Layer | Owner |
|----------------|-------|-------|
| Admission `prior-shape-intake-sealed` | Policy | engine |
| Agent receipt required on seal | Policy | engine |
| Route to present vs examine gate from `open_clarifying_questions_count` | Policy | engine (flow `when:`) |
| Examination conversation, draft AC, questions, counters | Judgment | steward |
| `visit.state_patch` for examination state fields | Mechanism | steward (CLI; spec in operations) |
| Agent receipt draft/seal, transition | Mechanism | steward |
| `allow.user.ask` | Presentation | cli / steward chat |

### Test matrix

| Test | What it proves |
|------|----------------|
| `acceptance/features/shape_examine.feature` | Fast lane vs gate routing; context; refine loop entry |
| `acceptance/features/shape_examine_gate.feature` | Gate adjacency |
| `acceptance/features/shape_present_gate.feature` | Reject → examine |
| `acceptance/features/shape_intake.feature`, `shape_phase_e2e.feature` | Upstream intake |
| `acceptance/features/run_context.feature`, `catalog_build.feature` | Context and catalog |
| `unit/test_node_operations.py` | Examine `operations.yaml` load and routing targets |
| `unit/test_transition_policy.py` | Intake policy does not apply to examine |

---

## `shape.examine.gate`

### Authoritative assets

| Asset | Registry ref |
|-------|----------------|
| Instructions | `registry:nodes/shape.examine.gate/instructions.md` |
| Flow node | `factory-flow.yaml` → `shape.examine.gate` (`decider: user`) |

### Checks and connections

| Hook | Checks |
|------|--------|
| `on_examine` | `prior-examine-sealed` |

**Options:** `accept`, `reject`. **Prompt** in flow YAML (open questions remain).

**Out:** `accept` → `shape.present`; `reject` → `shape.examine`.

### Responsibility ownership

| Responsibility | Layer | Owner |
|----------------|-------|-------|
| Gate definition, options, connection `decisions` | Policy | registry |
| `prior-examine-sealed` | Policy | engine |
| Present gate prompt text to user | Presentation | steward (chat); prompt source registry |
| `gate decide` | Mechanism | cli |
| Seal gate visit and admit next node | Mechanism | engine |

### Test matrix

| Test | What it proves |
|------|----------------|
| `acceptance/features/shape_examine_gate.feature` | accept/reject routing, context |
| `acceptance/features/shape_examine.feature` | Entry when open questions remain |
| `acceptance/features/run_context.feature` | Gate context packet |

---

## `shape.present`

### Authoritative assets

| Asset | Registry ref |
|-------|----------------|
| Instructions | `registry:nodes/shape.present/instructions.md` |
| Worker | `registry:agents/shape-presenter.md` + `registry:workers/shape-presenter/contract.yaml` |
| Flow node | `factory-flow.yaml` → `shape.present` |

### Checks and connections

| Hook | Checks |
|------|--------|
| `on_examine` | `prior-examine-sealed` |
| `on_seal` | `agent-receipt-sealed` |

**Produces:** artifact `presentation` (markdown).

**Out:** `shape.present-to-shape.present.gate` on `completed`.

**In:** examine fast lane or `shape.examine.gate` accept.

### Responsibility ownership

| Responsibility | Layer | Owner |
|----------------|-------|-------|
| Seal-time agent receipt | Policy | engine |
| Plan/AC presentation content, PROCEED/BLOCKED | Judgment | worker (`shape-presenter`) |
| Publish presentation artifact, patch `presented_ac`, receipt seal, transition | Mechanism | steward |
| Context packet and artifact publish CLI | Presentation | cli |

### Test matrix

| Test | What it proves |
|------|----------------|
| `acceptance/features/shape_present.feature` | Publish, seal, transition to present gate |
| `acceptance/features/shape_examine.feature`, `shape_examine_gate.feature` | Upstream paths |
| `acceptance/features/shape_present_gate.feature`, `shape_phase_e2e.feature` | Downstream gate |
| `acceptance/features/run_context.feature` | Context fields |

---

## `shape.present.gate`

### Authoritative assets

| Asset | Registry ref |
|-------|----------------|
| Instructions | `registry:nodes/shape.present.gate/instructions.md` (two-turn presentation + decide) |
| Flow node | `factory-flow.yaml` → `shape.present.gate` (`decider: user`) |

### Checks and connections

| Hook | Checks |
|------|--------|
| `on_examine` | `prior-present-sealed` |

**Options:** `reject`, `accept`. Reads `presented_ac`, presentation artifact.

**Out:** `reject` → `shape.examine`; `accept` → `shape.record`.

### Responsibility ownership

| Responsibility | Layer | Owner |
|----------------|-------|-------|
| Gate options and routing | Policy | registry |
| `prior-present-sealed` | Policy | engine |
| Full presentation + AC presentation (turn 1), no `gate decide` same turn | Presentation | steward |
| User decision via `gate decide` (turn 2) | Mechanism | cli + steward |

### Test matrix

| Test | What it proves |
|------|----------------|
| `acceptance/features/shape_present_gate.feature` | accept → record; reject → examine |
| `acceptance/features/shape_present.feature`, `shape_phase_e2e.feature` | Adjacent steps |
| `acceptance/features/run_context.feature` | Gate context |

---

## `shape.record`

### Authoritative assets

| Asset | Registry ref |
|-------|----------------|
| Instructions | `registry:nodes/shape.record/instructions.md` |
| Worker | `registry:agents/shape-recorder.md` + `registry:workers/shape-recorder/contract.yaml` |
| Flow node | `factory-flow.yaml` → `shape.record` |

### Checks and connections

| Hook | Checks |
|------|--------|
| `on_examine` | `prior-present-sealed` |
| `on_seal` | `approved-ac-recorded`, `agent-receipt-sealed` |

**Produces:** artifact `plan`; writes `workspace:plan.md`.

**Out:** `shape.record-to-shape.record.gate` on `completed`.

### Responsibility ownership

| Responsibility | Layer | Owner |
|----------------|-------|-------|
| `approved-ac-recorded` check (`approved_ac_version >= 1`) | Policy | engine |
| Plan draft, approved AC freeze fields | Judgment | worker (`shape-recorder`) |
| Publish plan artifact, state patches for approved AC digest/version, seal, transition | Mechanism | steward |

### Test matrix

| Test | What it proves |
|------|----------------|
| `acceptance/features/shape_record.feature` | Record path, seal checks |
| `acceptance/features/shape_present_gate.feature`, `shape_record_gate.feature`, `shape_phase_e2e.feature` | Shape tail |
| `acceptance/features/run_context.feature` | Context |

---

## `shape.record.gate`

### Authoritative assets

| Asset | Registry ref |
|-------|----------------|
| Instructions | `registry:nodes/shape.record.gate/instructions.md` (two-turn presentation + decide) |
| Flow node | `factory-flow.yaml` → `shape.record.gate` (`decider: user`) |

### Checks and connections

| Hook | Checks |
|------|--------|
| `on_examine` | `prior-shape-record-sealed`, `approved-ac-recorded` |

**Options:** `accept`, `hold`.

**Out:** `accept` → `execute.start` (execute phase; out of Shape inventory). `hold` seals the gate visit with no outgoing connection (no advance to execute).

### Responsibility ownership

| Responsibility | Layer | Owner |
|----------------|-------|-------|
| Preconditions on examine | Policy | engine |
| Living plan + approved AC presentation (turn 1) | Presentation | steward |
| `gate decide` accept/hold | Mechanism | cli + steward |

### Test matrix

| Test | What it proves |
|------|----------------|
| `acceptance/features/shape_record_gate.feature` | Gate routing and context |
| `acceptance/features/shape_record.feature`, `shape_phase_e2e.feature` | Record → gate |
| `acceptance/features/run_context.feature` | Context |

---

## Known gaps (later phases; not fixed in Phase 0)

| Gap | Notes |
|-----|--------|
| Job host + `advance()` | **Implemented** (Phases 2–3); baseline inventory predates engine/host |
| `operations.yaml` is declarative only | Steward (or Cursor) executes steps; no registry executor |
| Intake still requires agent/worker for PROCEED/BLOCKED | Phase 1 target: deterministic intake without agent |
| Examination routing counter set by steward judgment | Phase 1+: structured questions; engine-derived counts |
| Steward orchestrates CLI sequence | User path should move to engine/host; stewards become compatibility |
| `recommended_next_state` on agent receipts | Still used in tests/fixtures; not engine routing authority |
| Generated `docs/nodes/shape.intake.md` / `shape.examine.md` may still link to removed `instructions.md` | Docgen paths (`cli_docgen.py`) — update in a docs pass |
| Concepts docs (`graph.md`, `registry.md`, `capabilities.md`) mention `instructions.md` for intake | Editorial drift |
| Durable ledger / snapshot recovery | **Partial (P7)** — `ledger.jsonl` append before snapshot; inline migration and ledger-based recovery; full materialized-state replay not implemented |
| No user-facing `foundry shape` CLI | Phase 5 |
| Model adapter / validated examination JSON result | Phase 4 |
| `shape.present` / `shape.record` not split into `judgment.md` + `operations.yaml` | Optional parity with intake/examine extraction |

---

## Phase 0 proof statement

| Criterion | Status |
|-----------|--------|
| Each Shape instruction asset identified and bound in flow/catalog | Met |
| Responsibilities mapped to Judgment / Mechanism / Policy / Presentation with owner | Met (tables above) |
| Current behavior covered by acceptance + unit tests | Met (matrices above); examine operations load test added for parity with intake |

---

## Verification commands (Phase 0)

From `.cursor/foundry/cli`:

```text
python -m pytest tests/unit/test_node_operations.py tests/unit/test_transition_policy.py -q
python -m pytest tests/acceptance/test_shape_*.py -q
```

Expected: exit code `0`.
