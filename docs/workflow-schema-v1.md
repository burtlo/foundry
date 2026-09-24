# Foundry Workflow Schema v1

Status: **draft** (design definition — not wired to current `factory-flow.yaml`)

Companion: workflow schema v1 canvas walkthrough (IDE canvas `workflow-schema-v1`)

PoC implementation reference: `.cursor/foundry/flows/factory-flow.yaml`, `docs/v1-spec.md`

---

## Charter

Define a steady, logically complete schema for a workflow engine with:

- **Nodes** (steps and gates) sharing one accountability lifecycle
- **Checks** that evaluate reality only
- **Policies** that map check results to actions
- **Actions** as the only flow-control mechanism
- A clean split between registry (authored YAML) and visit (engine-written instance)

This document does not require compatibility with the current PoC tooling.

---

## Anchor contract

```text
Checks evaluate reality.
Policies decide what to do.
Actions control workflow.
Gates make decisions.
Steps produce work.
```

---

## Architecture

```text
Workflow
  → Nodes

Node
  → kind (step | gate)
  → produces (artifact | decision)
  → Lifecycle (examined → opened → closed → sealed)
  → Checks (at transition hooks: examine, open, close, seal)
  → Policies (onPass | onFail | onNotApplicable → actions[])
  → Evidence / Receipts

Node types
  → step  — produces work artifacts
  → gate  — produces decisions (stateful; checks remain stateless)
```

---

## Lifecycle

Every executable node shares the same four states.

| State | Meaning | Typical actor |
|-------|---------|---------------|
| `examined` | Visit exists; eligibility may be evaluated before work starts | Engine |
| `opened` | Work or interaction in progress | Steward |
| `closed` | Node claims completion (artifacts ready or decision recorded) | Steward |
| `sealed` | Engine verified and accepted completion | Engine |

```text
examined → opened → closed → sealed
```

### `closed` ≠ `sealed`

- **Closed** — “I believe I am done.”
- **Sealed** — “You are verified as complete.”

Seal outcomes (set only when `lifecycle == sealed`):

| Outcome | Meaning |
|---------|---------|
| `completed` | Work or decision verified |
| `not_applicable` | Node did not apply (`skip`) |
| `failed` | Verification failed |
| `disqualified` | Node ruled out by policy |

A node may reach `examined` and never `opened` when a pre-work hook policy applies `skip` or `finish`.

### Why `examined` instead of `received`

`examined` is the admission-and-eligibility phase: the visit is on the record, and examine-hook checks run before open. It does **not** mean “all checks have already passed.”

`received` is equally valid semantically; `examined` was chosen to avoid the `ie` / `ei` spelling ambiguity in authoring and conversation. If that ambiguity becomes a problem in practice, `admitted` is a neutral alternative with the same meaning.

---

## Checks

Checks are **pure, stateless** evaluation functions. They answer: *is something true?*

### Results (closed set)

| Result | Meaning |
|--------|---------|
| `pass` | Condition satisfied |
| `fail` | Condition not satisfied |
| `notApplicable` | This check does not apply to this visit |

Checks **never** return flow-control outcomes (`skip`, `halt`, etc.). Those are **actions**.

### Check body

Each check in the catalog has exactly one body (the body implies how it runs — no separate `kind` field):

| Body | Evaluation |
|------|------------|
| `when` | Expression against `config`, `state`, `visit`, `visits` |
| `command` | Foundry CLI command; exit 0 = pass |
| `path` | File exists at `registry:`, `run:`, or `workspace:` path |

### Who runs checks

Runner is **implied by lifecycle hook**, not declared per check:

| Hook | Runner |
|------|--------|
| `examine` | Engine |
| `open` | Engine |
| `close` | Engine |
| `seal` | Engine |

The steward acts only while `lifecycle == opened`. All transition checks are engine-owned.

### Recording

Every check evaluation is appended to the run ledger (`check.recorded`) before any policy runs:

```yaml
# ledger event (illustrative)
type: check.recorded
payload:
  hook: open
  check_id: repository-exists
  result: pass
  output: { exit_code: 0 }
```

---

## Policies and actions

### Policies

Policies map a check result to one or more **actions**. Policies are composable; order matters.

Omit `onPass`, `onFail`, and `onNotApplicable` to use defaults (see below).

```yaml
lifecycle:
  examine:
    checks:
      - id: supported-work-item
        onFail:
          actions:
            - action: skip
              reason: "Work item type not supported"
```

### Default policies (implicit — do not author)

| Result | Default actions |
|--------|-----------------|
| `pass` | `[{ action: continue }]` |
| `fail` | `[{ action: halt }]` |
| `notApplicable` | `[{ action: continue }]` |

When the last check in a hook ends with `continue`, the engine proceeds to the next hook automatically. No `advance` action is required for normal flow.

### Action catalog (v1)

Eight actions. Each action is valid only on specific hooks (schema-enforced at `flow validate`).

| Action | Effect | Valid hooks | Stops hook batch? |
|--------|--------|-------------|-------------------|
| `continue` | Proceed to next check in this hook | all | No |
| `satisfy` | Hook satisfied; skip remaining checks; run next hook | all | Yes (hook only) |
| `skip` | Seal `not_applicable`; route forward; steward never works | `examine`, `open` | Yes (visit) |
| `finish` | Seal `completed`; route forward; evidence already present | `examine`, `open` | Yes (visit) |
| `reopen` | `closed` → `opened`; steward must fix and close again | `seal` | Yes |
| `halt` | Freeze run | all | Yes |
| `escalate` | Pause run; require operator acknowledgment | all | Yes |
| `disqualify` | Seal `disqualified`; route per edges/outcomes | all | Yes (visit) |

**Removed from earlier drafts:** `passThrough` (merged into `skip`), `advance` (use `satisfy` or implicit hook completion), `return` (renamed `reopen`), `retry` (implicit — hold phase and re-invoke), `complete` (split into `finish` vs normal seal), `wait` (deferred — synchronous v1 uses `escalate` only), `severity` (deferred — use `reason` and visit evidence).

### Why `passThrough` became `skip`

`passThrough` only made sense before `opened`: seal without steward work. The same is true at the `open` hook (checks run before `lifecycle` becomes `opened`). Using `passThrough` at `close` or `seal` would lie about what happened.

One action — **`skip`** — covers both cases:

- At **`examine`**: visit stays unopened; seals `not_applicable`; routes forward.
- At **`open`**: open-hook checks finish; steward never starts; same outcome.

Checks evaluated before `skip` are still recorded. Audit shows what was tested and why the node was skipped.

`flow validate` **rejects** `skip` and `finish` on `close` or `seal` hooks.

### `skip` vs `finish`

Both exit early without steward work. They differ in **seal outcome**:

| Action | Outcome | When to use |
|--------|---------|-------------|
| `skip` | `not_applicable` | Node does not apply to this run (unsupported work item, feature disabled) |
| `finish` | `completed` | Work already satisfied; evidence exists (receipt on disk, prior visit completed) |

Example — review disabled (`skip`):

```yaml
examine:
  checks:
    - id: review-enabled
      onFail:
        actions:
          - action: skip
            reason: "Review disabled in manifest"
```

Example — review already done (`finish`):

```yaml
examine:
  checks:
    - id: review-receipt-present
      onPass:
        actions:
          - action: finish
            reason: "Review receipt already present"
```

If `finish` is wrong and evidence is missing, use normal flow: let checks fail and `halt`, or route to a node that produces the evidence.

### `satisfy` (replaces `advance`)

`satisfy` does **not** seal or route. It ends the current hook early and runs the next hook in the engine procedure.

Use when an early check passes and remaining checks in the same hook are unnecessary:

```yaml
examine:
  checks:
    - id: strict-manifest-version
      onPass:
        actions:
          - action: satisfy
    - id: optional-legacy-check
    - id: optional-legacy-check-2
```

If `strict-manifest-version` is `notApplicable`, defaults apply: `continue` runs the optional checks.

### `reopen` (replaces `return`)

`reopen` is only valid on the **`seal`** hook. The steward has `closed` the visit; a seal check failed; the visit goes back to **`opened`** so the steward can fix evidence and close again.

```yaml
seal:
  checks:
    - id: ticket-file-present
      onFail:
        actions:
          - action: reopen
            reason: "Ticket file missing at seal"
```

This is **not** routing to another node. It is the same `visit_id`, same steward context. The run ledger records each lifecycle change — see [Run history](#run-history).

**Repair loops across nodes** (sub-agent finished but engine already routed — the failure mode you described) are prevented by the engine: **no routing until seal succeeds**. `reopen` handles “closed too early, evidence not ready.” Sending work to a repair agent and returning to `execute.build` is an **edge** to the same or another node (new visit), not a `reopen` action.

### `escalate`

Pauses the run and requires operator acknowledgment (CLI or UI). The visit stays at its current lifecycle state until the operator clears the escalation. Composable with other actions only when documented; typical use is a single `escalate` with `reason`.

Replaces the earlier `escalate` + `wait` pair. No async event subscription in v1.

### `disqualify`

Seals the visit `disqualified` and routes forward. Downstream nodes may test `history.last(visit.sealed, node_id='…').outcome == 'disqualified'` in examine checks.

### `reason` metadata

| Field | Required on | Purpose |
|-------|-------------|---------|
| `reason` | `skip`, `finish`, `halt`, `escalate`, `disqualify`, `reopen` | Human-readable audit trail |

`severity` is deferred. Warnings belong in check `output` or evidence records where the next steward can read them — not as a parallel log-level field on the action.

### `notApplicable` result vs `fail` + `skip`

| Pattern | When to use |
|---------|-------------|
| `notApplicable` + default `continue` | This check item does not apply; sibling checks still run |
| `fail` + `skip` | Condition evaluated false; whole node should not run |

Example: optional lint config absent → check **notApplicable**, **continue**.  
Example: review disabled → check **fail**, policy **skip**.

### Check ordering within a hook

Checks in a hook run in **declaration order**. After each check:

1. Append `check.recorded` to the ledger
2. Append `policy.applied` and run policy actions in order
3. Terminal visit actions (`skip`, `finish`, `halt`, `disqualify`, `escalate`) stop the hook and end `enter(node)` processing
4. `satisfy` stops the hook but continues `enter(node)` at the next hook
5. `reopen` stops the hook and returns the visit to `opened`
6. `continue` proceeds to the next check

Complex branching belongs in one `when` check or a dedicated predicate — not inferred across checks.

Example — order matters:

```yaml
examine:
  checks:
    - id: optional-repo-check
      onFail:
        actions:
          - action: continue
    - id: manifest-valid
      onFail:
        actions:
          - action: halt
            reason: "Manifest invalid"
```

### Hook validity matrix

| Action | examine | open | close | seal |
|--------|:-------:|:----:|:-----:|:----:|
| `continue` | ✓ | ✓ | ✓ | ✓ |
| `satisfy` | ✓ | ✓ | ✓ | ✓ |
| `skip` | ✓ | ✓ | — | — |
| `finish` | ✓ | ✓ | — | — |
| `reopen` | — | — | — | ✓ |
| `halt` | ✓ | ✓ | ✓ | ✓ |
| `escalate` | ✓ | ✓ | ✓ | ✓ |
| `disqualify` | ✓ | ✓ | ✓ | ✓ |

---

## Node kinds

### Step

Produces work artifacts.

```yaml
- id: shape.intake
  kind: step
  produces:
    type: artifact
    artifacts: [ticket, intake-receipt]
  instructions: registry:steps/shape-intake.md
  reads: { ... }
  allow: { ... }
  lifecycle:
    examine:
      checks: []
    open:
      checks:
        - id: repository-exists
    close:
      checks: []
    seal:
      checks:
        - id: ticket-file-present
          onFail:
            actions:
              - action: reopen
                reason: "Ticket file missing at seal"
  worker:
    prompt: registry:agents/intake-checker.md
```

### Gate

Produces a decision. Stateful (prompt, pending choice, multi-turn interaction). Checks on a gate remain stateless.

```yaml
- id: acceptance-review
  kind: gate
  produces:
    type: decision
    options: [approve, reject, needsChanges]
  prompt: registry:prompts/acceptance-review.md
  lifecycle:
    examine:
      checks:
        - id: prior-build-sealed
          onFail:
            actions:
              - action: halt
                reason: "Build not sealed"
  outcomes:
    approve: verify.test
    reject: shape.examine
    needsChanges: execute.implement
```

Gate routing uses `outcomes` only. Step routing uses edges (below).

### Authoring defaults (omit empty fields)

Registry YAML omits any field whose value equals the default. `flow validate` treats missing and empty as equivalent for defaulted fields.

| Field | Default when omitted |
|-------|----------------------|
| `reads.config` | `[]` — no config namespaces |
| `reads.state` | `[]` — no extra state keys beyond what checks need |
| `reads.files` | `[]` — no file reads |
| `allow.state` | `[]` — only implicit node scope (below) |
| `allow.files.write` | `[]` — no file writes |
| `allow.cli` | `["transition"]` on non-terminal steps — steward may call engine seal/route |
| `allow.cli` on `terminal: true` | `[]` — no transitions |
| `allow.agents` | `[]` — no extra agents beyond `worker` |
| `allow.user.ask` | `false` |
| `allow.user.decide` | `false` on steps; `true` on `kind: gate` |
| `lifecycle.examine/open/close/seal` | `{ checks: [] }` — hook runs, no checks |
| `lifecycle` | `{}` — all hooks empty |
| `produces.artifacts` | `[]` when `type: artifact` |

Do **not** author `files: []`, `agents: []`, `cli: [transition]`, or `user: { ask: false, decide: false }` when the defaults apply.

### Implicit node state scope

The engine always grants the steward write access to **`state.steps.<node_id>.*`** for the active visit (status, receipt_id, gate_decision, intake_receipt_id, report, etc.). Authors list only **additional root-level** `state.*` keys in `allow.state`.

```yaml
# Good — only cross-node domain keys
allow:
  state: [ticket, run_slug, clarifying_questions]
  files:
    write: [run:ticket.json]

# Redundant — do not repeat steps.shape.intake.*
allow:
  state: [steps.shape.intake.status, steps.shape.intake.receipt_id, ticket]
```

`worker` implies the contract’s agent may run; repeating it under `allow.agents` is unnecessary unless launching **additional** agents beyond `worker`.

### `transition` CLI

Default `allow.cli: [transition]` means the steward may ask the engine to close/seal and route — not “free navigation.” The engine still enforces lifecycle checks, receipts, and edges. Terminal nodes (`terminal: true`) default to **no** CLI capabilities.

### Lifecycle hook naming (discussion)

Hooks are currently `examine`, `open`, `close`, `seal`. A possible readability improvement is `on_examine`, `on_open`, `on_close`, `on_seal` (event-style names). **Not adopted in v1**; revisit if authors confuse hooks with lifecycle **states** (`examined`, `opened`, …).

---

## Routing

### After seal

When a visit seals with `completed` or `not_applicable`:

1. **Explicit target** — if the node declares `onSeal.target`, route there. This takes precedence.
2. **Gate outcomes** — gate nodes route via `outcomes[decision]`.
3. **Edges** — step nodes: evaluate outgoing `edges` whose `when` is true; lowest `priority` wins.

### Edge rules (steps)

```yaml
edges:
  - from: shape.intake
    to: shape.examine
    when: always
    priority: 10
```

| Rule | Definition |
|------|------------|
| Winner | Lowest `priority` among edges whose `when` is true |
| Tie | Two winners at same priority → definition error |
| Zero matches | Definition error unless node is `terminal: true` |
| Bare `when` | Omitted `when` means `always`; at most one such edge per `from` |

### Routing conflict (explicit vs edge)

A step may declare both an edge and `onSeal.target`. **Explicit `onSeal.target` wins.**

```yaml
shape.present:
  onSeal:
    target: shape.record    # explicit — used after seal
edges:
  - from: shape.present
    to: shape.examine       # ignored for routing after seal
    when: "decision == 'refine'"
    priority: 10
```

Use explicit `onSeal.target` when seal always goes to one place; use edges when routing depends on `state` or `decision`. Do not define conflicting targets without `onSeal` — that is a definition error at `flow validate` time.

Gate nodes must not also define step-style edges from the same node; `outcomes` is the sole route table for gates.

---

## Run history

### Relation to PoC persistence

The PoC (`kwiktrip/.github-private-eval-foundry-approach` — `foundry.py`) already writes **three kinds of run data**. The v1 ledger is not a fourth parallel system; it **formalizes and extends** what `events.jsonl` already does.

| PoC artifact | Path | What it stores today | Role in schema v1 |
|--------------|------|----------------------|-------------------|
| **Event log** | `{run_dir}/events.jsonl` | Append-only JSONL via `append_event()` / `make_event()` — `run_started`, `state_transition`, `gate_presented`, `gate_resolved`, `subagent_launched`, `subagent_completed`, `cli_invoked`, `external_operation`, … | **Becomes the ledger.** Same file, richer event types (`lifecycle.changed`, `check.recorded`, `policy.applied`, `visit.sealed`, …) and `visit_id` on every row. |
| **Run state** | `{run_dir}/state.json` | Mutable snapshot (`factory-run-state.schema.json`): `current_step`, `steps.{id}.status`, ticket/AC/plan fields, `examination_round`, `rework.validator_loops`, … | **Resume cache + domain state.** Still updated for fast reads and steward context. **Not** the audit source of truth for workflow history. `steps.*.status` becomes a derived/materialized summary, not the history itself. |
| **Receipts** | `{run_dir}/receipts/*.json` | `agent-receipt.schema.json`, `intake-receipt.schema.json` — sealed work evidence from agents and intake | **Unchanged as files.** Ledger appends `receipt.linked` (path + `receipt_id`) when a receipt is sealed. Intake receipt `checks[]` align with ledger `check.recorded` events. |

**What the PoC does on `transition` today** (simplified):

1. Validates gates, receipts, edges.
2. Updates `state.json`: marks `from_step` completed, `to_step` in_progress, sets `current_step`.
3. Appends one `state_transition` event to `events.jsonl` (`from_step`, `to_step`, `evidence_refs`).
4. Optionally increments `state.rework.*` counters (`record_rework_on_transition`).

**What changes in v1:**

- Every lifecycle move, check, and policy — not only transitions — appends a ledger row.
- `foundry run history` reads `events.jsonl` in full (PoC’s `run show` emphasizes the `state.json` summary instead).
- Rework/loop counts come from querying ledger events, not `state.rework` fields (those PoC counters are what we are replacing).
- `visit_id` groups events for one passage through a node; `reopen` appends more rows on the **same** `visit_id` (PoC has no equivalent — a failed seal today is mostly reflected only in mutable `step_evidence`).

**What does not duplicate:**

| Concern | Ledger | state.json | Receipt files |
|---------|--------|------------|---------------|
| Workflow audit trail (what happened, in order) | ✓ authoritative | summary only | — |
| Steward working data (ticket, AC, questions) | — | ✓ | — |
| Agent work product (exploration, decisions, commands) | pointer event | receipt_id ref | ✓ authoritative |
| Current position (`current_step` / active visit) | derivable | ✓ fast path | — |

Schema v1 adds ledger rows the PoC never recorded (per-check results, lifecycle phases, policies). It does **not** replace receipt files or domain fields in `state.json`.

---

The authoritative record of a run is an **append-only event ledger** (`events.jsonl`). Nothing is summarized at write time. The engine appends one event per observable change; it never increments an `attempt` counter or rewrites prior rows.

Flow YAML does **not** declare `limits.loops` or counter fields on edges. Any count (“how many times did we seal `shape.examine` with `continue`?”) is computed by querying the ledger after the fact.

### CLI

| Command | Output |
|---------|--------|
| `foundry run history` | Full ledger, chronological, human-readable table (reads `events.jsonl`) |
| `foundry run history --json` | Same ledger as a JSON array (pipe to `jq`) |
| `foundry run history --summary` | **Derived** one-line-per-visit collapse (optional; not stored) |
| `foundry run show` (PoC today) | **Snapshot** from `state.json` — current step, summarized `step_evidence` |

`foundry run history` is the general “what happened on this run?” command. It is not a node list with attempt numbers. In v1, `craft-status` / `run show` may include a snapshot **plus** a link to full history; the ledger remains the audit source.

### Event ledger (source of truth)

Each row is immutable once written:

```yaml
event:
  seq: int              # 1-based, monotonic for this run
  at: timestamp         # ISO-8601
  visit_id: string      # correlation id; stable for one passage through a node
  node_id: string
  type: string          # see event types below
  payload: object       # type-specific; never overwrites prior events
```

**Event types** (illustrative closed set):

| type | payload (examples) | When appended | PoC analogue |
|------|-------------------|---------------|--------------|
| `visit.admitted` | `routed_from_visit_id`, `routed_from_node_id`, `edge_id` | `enter(node)` creates visit | `state_transition` (landing step only) |
| `lifecycle.changed` | `from`, `to` (`examined` \| `opened` \| `closed` \| `sealed`) | Every lifecycle transition | (new — PoC only updates `state.steps.*.status`) |
| `check.recorded` | `hook`, `check_id`, `result`, `output` | After each check evaluation | intake receipt `checks[]` at seal time |
| `policy.applied` | `check_id`, `result`, `actions[]` | After policy runs | (new) |
| `visit.sealed` | `outcome`, `reason` | Visit reaches terminal seal | `step_evidence.status = completed` |
| `visit.skipped` | `outcome: not_applicable`, `reason` | `skip` / `finish` early exit | `step_evidence.status = skipped` |
| `route.taken` | `to_node_id`, `edge_id` or `outcome` | After seal, before next `visit.admitted` | `state_transition` |
| `receipt.linked` | `receipt_id`, `path`, `schema` | Receipt file sealed | implicit in transition evidence_refs |
| `gate.presented` | `options`, `prompt_ref` | Gate shown to human | `gate_presented` |
| `gate.resolved` | `decision` | Human chooses | `gate_resolved` |
| `subagent.launched` | `agent`, `launch_id` | Worker started | `subagent_launched` |
| `subagent.completed` | `receipt_id`, `status` | Worker finished | `subagent_completed` |
| `escalation.raised` | `reason` | `escalate` action | (new) |
| `escalation.cleared` | `operator` | Operator acknowledges | (new) |

There is **no** `retry` event type in v1. PoC `state_transition` rows remain valid ledger events during migration; new type names are additive.

### Human-readable example (`foundry run history`)

Abbreviated run: intake with one `reopen`, then examine twice (continue loop), then present.

```text
seq  visit_id  node_id         type                 detail
───  ────────  ──────────────  ───────────────────  ─────────────────────────────────────
  1  v-001     shape.intake    visit.admitted       entry
  2  v-001     shape.intake    lifecycle.changed    → examined
  3  v-001     shape.intake    check.recorded       open repository-exists pass
  4  v-001     shape.intake    lifecycle.changed    → opened
  5  v-001     shape.intake    lifecycle.changed    → closed
  6  v-001     shape.intake    check.recorded       seal ticket-file-present fail
  7  v-001     shape.intake    policy.applied       reopen "Ticket file missing"
  8  v-001     shape.intake    lifecycle.changed    examined → opened   ← same visit_id
  9  v-001     shape.intake    lifecycle.changed    → closed
 10  v-001     shape.intake    check.recorded       seal ticket-file-present pass
 11  v-001     shape.intake    lifecycle.changed    → sealed
 12  v-001     shape.intake    visit.sealed         outcome completed
 13  v-001     shape.intake    route.taken          → shape.examine
 14  v-002     shape.examine   visit.admitted       routed_from v-001
 15  v-002     shape.examine   lifecycle.changed    → examined
 16  v-002     shape.examine   check.recorded       examine prior-intake-sealed pass
 17  v-002     shape.examine   lifecycle.changed    → opened
 18  v-002     shape.examine   lifecycle.changed    → closed
 19  v-002     shape.examine   visit.sealed         outcome completed, decision continue
 20  v-002     shape.examine   route.taken          → shape.examine (same node, new visit)
 21  v-003     shape.examine   visit.admitted       routed_from v-002
 22  v-003     shape.examine   lifecycle.changed    → examined
 23  v-003     shape.examine   lifecycle.changed    → opened
 24  v-003     shape.examine   lifecycle.changed    → closed
 25  v-003     shape.examine   visit.sealed         outcome completed, decision present
 26  v-003     shape.examine   route.taken          → shape.present
 27  v-004     shape.present   visit.admitted       routed_from v-003
```

**How to read this:**

- **`reopen`** (rows 6–8): same `visit_id` (`v-001`). Seal failed; policy `reopen`; lifecycle goes back to `opened`. No new visit; no attempt counter. The ledger shows the full back-and-forth.
- **Examine loop** (rows 19–21): new `visit_id` (`v-003`) because routing took an edge back to `shape.examine`. Same `node_id`, different visit. Count “continue” loops with `jq`, not an engine field.
- **Skip** (not shown): would show `visit.skipped` then `route.taken` without any `lifecycle.opened` row for that visit.

### JSON example (`foundry run history --json`)

```json
{
  "run_id": "run-2026-09-23-abc",
  "flow_id": "implementation",
  "events": [
    {
      "seq": 6,
      "at": "2026-09-23T22:01:04Z",
      "visit_id": "v-001",
      "node_id": "shape.intake",
      "type": "check.recorded",
      "payload": {
        "hook": "seal",
        "check_id": "ticket-file-present",
        "result": "fail",
        "output": { "path": "run:ticket.json", "exists": false }
      }
    },
    {
      "seq": 7,
      "at": "2026-09-23T22:01:04Z",
      "visit_id": "v-001",
      "node_id": "shape.intake",
      "type": "policy.applied",
      "payload": {
        "check_id": "ticket-file-present",
        "result": "fail",
        "actions": [{ "action": "reopen", "reason": "Ticket file missing" }]
      }
    },
    {
      "seq": 8,
      "at": "2026-09-23T22:01:04Z",
      "visit_id": "v-001",
      "node_id": "shape.intake",
      "type": "lifecycle.changed",
      "payload": { "from": "closed", "to": "opened" }
    }
  ]
}
```

### Derived counts (not stored)

```bash
# How many sealed examine visits chose continue?
foundry run history --json | jq '[.events[] | select(.type=="visit.sealed" and .node_id=="shape.examine" and .payload.decision=="continue")] | length'

# Last three examine visits (by visit.admitted seq)
foundry run history --json | jq '...'
```

Checks in flow YAML query the same ledger through the `history` namespace (not pre-aggregated visits):

```yaml
checks:
  reshape-limit:
    when: "history.count(visit.sealed, node_id='shape.examine', decision='continue') < 3"
```

```yaml
examine:
  checks:
    - id: reshape-limit
      onFail:
        actions:
          - action: escalate
            reason: "Examine continue loop exceeded; operator acknowledgment required"
```

`history.last(...)`, `history.count(...)`, and `history.events(filter)` are expressions over the ledger. The engine does not maintain parallel counter state.

---

## Path grammar

| Prefix | Root |
|--------|------|
| `registry:` | Flow bundle (`.cursor/foundry`) |
| `run:` | Current run directory |
| `workspace:` | App repository |

No bare filenames. No `{run_dir}` token.

---

## Registry document (author)

```yaml
flow:
  id: implementation
  version: 1
  entry: shape.intake

  checks:
    repository-exists:
      command: app.validate
    ticket-file-present:
      path: run:ticket.json
    supported-work-item:
      when: "config.work_item.kind in ['story', 'bug']"
    review-enabled:
      when: "config.review.enabled"
    prior-intake-sealed:
      when: "history.last(visit.sealed, node_id='shape.intake').outcome == 'completed'"

  nodes:
    - id: shape.intake
      kind: step
      produces:
        type: artifact
        artifacts: [ticket, intake-receipt]
      instructions: registry:steps/shape-intake.md
      reads:
        config: [workspace, foundry]
        state: []
        files: []
      allow:
        state: [ticket, run_slug]
        files:
          write: [run:ticket.json]
        cli: [app.validate]
        agents: [intake-checker]
        user: { ask: false, decide: false }
      lifecycle:
        examine:
          checks: []
        open:
          checks:
            - id: repository-exists
        seal:
          checks:
            - id: ticket-file-present
              onFail:
                actions:
                  - action: reopen
                    reason: "Ticket file missing"
      worker:
        prompt: registry:agents/intake-checker.md

    - id: verify.code_quality
      kind: step
      produces:
        type: artifact
        artifacts: [review-receipt]
      instructions: registry:steps/verify-code-quality.md
      lifecycle:
        examine:
          checks:
            - id: review-enabled
              onFail:
                actions:
                  - action: skip
                    reason: "Review disabled in manifest"
        seal:
          checks:
            - id: review-receipt-present
              path: run:review-receipt.json

    - id: acceptance-review
      kind: gate
      produces:
        type: decision
        options: [approve, reject, needsChanges]
      prompt: registry:prompts/acceptance-review.md
      outcomes:
        approve: verify.test
        reject: shape.examine
        needsChanges: execute.implement

  edges:
    - from: shape.intake
      to: shape.examine
      when: always
      priority: 10
    - from: verify.code_quality
      to: verify.code_review
      when: always
      priority: 10
```

Omit nulls and empty defaults in authored YAML.

---

## Visit (correlation id, not a summary)

A **visit** is the engine’s grouping key for one passage through a node. It is identified by `visit_id`. The ledger is authoritative; the visit object is the **current snapshot** the engine needs to resume work (also derivable from ledger events for that `visit_id`).

```yaml
visit:
  id: string              # visit_id; stable from visit.admitted until visit.sealed or visit.skipped
  node_id: string
  kind: step | gate
  routed_from_visit_id: string | null   # from visit.admitted payload
  lifecycle: examined | opened | closed | sealed
  outcome: null | completed | not_applicable | failed | disqualified
  decision: string | null               # gates only
```

There is **no** `attempt` field. Returning to the same `node_id` after routing always creates a **new** `visit_id`. `reopen` does **not** create a new visit — it appends `lifecycle.changed` events on the same `visit_id`.

Check results, policies, evidence, and receipts appear only as **ledger events** (`check.recorded`, `policy.applied`, …), not as rolled-up arrays on the visit snapshot. That keeps one write path and a complete audit trail.

Optional `--summary` view (derived at read time):

```yaml
visit_summary:            # NOT stored; produced by foundry run history --summary
  visit_id: v-003
  node_id: shape.examine
  admitted_seq: 21
  sealed_seq: 25
  outcome: completed
  decision: present
  event_count: 5
```

---

## Engine procedure

```text
enter(node_id, routed_from_visit_id):
  visit = new Visit(node_id)
  ledger.append(visit.admitted, routed_from=routed_from_visit_id)
  set_lifecycle(visit, examined)      # ledger.append lifecycle.changed

  if not run_examine_hook(visit): return
  if not run_open_hook(visit): return

  set_lifecycle(visit, opened)
  steward(visit)                    # may span turns; gate interaction here

  set_lifecycle(visit, closed)
  if not run_close_hook(visit): return
  if not run_seal_hook(visit): return

  set_lifecycle(visit, sealed)
  ledger.append(visit.sealed, outcome=completed)   # unless skip/finish/disqualify
  route(visit)

run_hook(visit, hook):
  for check in node.lifecycle[hook].checks in order:
    row = evaluate(check)
    ledger.append(check.recorded, ...)
    outcome = apply_policy(row)     # ledger.append policy.applied
    if outcome == satisfy: return proceed_next_hook
    if outcome == reopen:
      set_lifecycle(visit, opened)  # same visit_id; ledger shows closed → opened
      return hold
    if outcome is terminal: return outcome
  return proceed_next_hook

set_lifecycle(visit, to):
  ledger.append(lifecycle.changed, from=visit.lifecycle, to=to)
  visit.lifecycle = to

route(visit):
  ledger.append(route.taken, to=...)
  if node.onSeal.target: enter(that, routed_from=visit.id)
  else if node.kind == gate: enter(outcomes[visit.decision], routed_from=visit.id)
  else: enter(winning_edge.to, routed_from=visit.id)
```

---

## Expression language

Namespaces: `config.*`, `state.*`, `visit.*`, `history.*`, `decision`

`visit.*` is the **current** visit snapshot during evaluation. `history.*` reads the append-only ledger (never pre-aggregated counters):

| Function | Meaning |
|----------|---------|
| `history.count(event_type, filter)` | Count matching ledger events |
| `history.last(event_type, filter)` | Most recent matching event payload |
| `history.visits(node_id)` | Distinct `visit_id` values for a node, in `seq` order |

Operators: `!`, `&&`, `||`, `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, parentheses  
Literals: `true`, `false`, `null`, strings, numbers  
Keyword: `always` (bare `when` on edges only)

---

## Left out of v1 schema

| Feature | Notes |
|---------|-------|
| Parallel flow tokens | Single unsealed visit at flow level; graph parallelism inside `execute.build` only |
| Per-item branches | Clean branch requirement serializes writers |
| `limits.loops` counters | Replaced by `history.*` queries over the event ledger |
| `attempt` on visits | Removed — loop counts are derived from ledger at query time |
| Config writes | Config readable; not writable in this definition |
| Timeouts / retries | Future fields on policies, not check results |
| `intro` / `outro` | Deferred hospitality payloads |

---

## Relation to PoC

| PoC (`factory-flow.yaml`) | Schema v1 |
|---------------------------|-----------|
| `steps:` | `nodes:` with `kind: step` |
| `gates:` catalog on steps | `kind: gate` nodes with `outcomes` |
| `requires:` | `lifecycle.examine.checks` |
| `actions.on_enter` | `lifecycle.open.checks` |
| `when_skip` | Removed — use `fail` + `skip` policy |
| `gate.outcomes` on step | Gate as its own node, or step-local gate protocol TBD in migration |
| Phase prefixes in step ids | Convention only; not enforced by engine |

**Registry artifact:** `.cursor/foundry/flows/factory-flow.yaml` (`version: 2`) is authored in this format. PoC `foundry.py flow validate` is not yet wired to `version: 2`; use JSON Schema validation until the CLI catches up.

Migration from PoC engine behavior to this schema is a separate effort. This document is the target definition.
