# Workflow-02 Step 0 — decision record

Binding policy decisions for workflow-02 blockers (missing step refs, `hold` routing, checks, routing strictness, engine gates, executor model, remediation findings, deliver terminal). Each entry states **chosen behavior** and **testable rationale**. Verification agents reject implementation that contradicts these without an updated decision.

Sources: [flows/implementation/registry.yaml](../../.cursor/foundry/flows/implementation/registry.yaml), [graph contract](../concepts/graph.md), [control-plane contract](../concepts/control-plane.md), [shape-execute-verify-gap-closure-plan.md](shape-execute-verify-gap-closure-plan.md).

---

## 1. Missing `registry:steps/...` instruction references (12 nodes)

**Chosen behavior:** Author step instructions under `.cursor/foundry/steps/` (or migrate to `registry:nodes/{id}/instructions.md` with a documented graph migration). Each file is derived from the node’s flow contract (reads/writes, checks, worker binding, receipts). Registry validation and `foundry dev docs` **fail closed** on unresolved `registry:` paths. Missing refs remain **blocking** for the slice that owns the node until the file exists and docgen is clean.

**Testable rationale:**

- Unit: resolver test asserts each of the twelve refs resolves to an on-disk file after the slice lands.
- Integration: `dev docs` exits 0 and produces no new broken links for those nodes.
- Negative: deliberately broken ref fails catalog/validation with a clear `REFERENCE_NOT_FOUND` (or equivalent) before run advancement.

**Delivery mapping:** slices 2A–2F per node ownership in the workflow plan.

---

## 2. `shape.record.gate` declares `hold` without a connection

**Chosen behavior:** `hold` is a **route to refinement**, not a persistent wait on the gate. Add a connection `shape.record.gate` → `shape.present` on `decisions: [hold]` (loop label e.g. `reshape_plan`). The gate visit completes with decision `hold`; the engine opens a new `shape.present` visit. `accept` remains the sole path to `execute.start`. No third “stuck on gate” state.

**Testable rationale:**

- Acceptance: user `decide hold` at record gate lands on `shape.present` with retained `approved_ac` superseded per contract (new present round).
- Static: route-coverage check lists exactly one eligible connection per gate outcome (`accept`, `hold`).
- Negative: `hold` with zero matching connection yields `definition_error`, not silent advance.

---

## 3. Declared command checks pass by default (hooks)

**Chosen behavior:** Implement **all** flow-declared command checks in `run_command_check` (minimum: `validate_git_clean_execute`, `validate_verify_context`, `ensure_execution_graph_reference`, `validate_build_exit`). Unknown check IDs and unknown commands **fail closed** with typed `check.recorded` result `fail` and halt/reopen per hook `on_fail`. Non-command checks (expression, receipt, history) must not default to `pass` without an evaluator.

**Testable rationale:**

- Unit: each command check has cases for pass, fail, and missing prerequisite; stub workspace fixtures.
- Unit: unregistered `check_id` returns fail, not pass.
- Integration: dirty git at `execute.intake` open prevents seal; invalid verify context blocks `verify.intake`.

---

## 4. Routing strictness (`when` expressions, exact-one route)

**Chosen behavior:** Implement the **declared expression grammar** from the graph contract with strict errors on parse/eval failure (no silent `false`). At runtime, after a seal or gate decision, **exactly one** connection may be eligible; zero or multiple matches produce `definition_error`, append evidence, and **do not** open a new visit. Remove “first eligible connection wins” for ambiguous sets.

**Testable rationale:**

- Unit: expression suite covers every `when` used in the flow registry (including loop counters and state fields).
- Unit: `select_connection` tests for 0, 1, and 2+ matches.
- Negative: unknown `when` substring fails validation at docgen or static route audit, not at runtime with false.

---

## 5. Engine gates vs user gates (`decider: engine`)

**Chosen behavior:** Introduce an **engine gate resolver** that runs after examine/seal checks: reads sealed, typed evidence (receipts, command exit codes, structured findings) and maps to one declared option. **User CLI must not** call `gate decide` on `decider: engine` nodes. Resolver outcome is recorded with provenance (rule id, evidence refs) and routes atomically with seal. Missing or contradictory evidence **halts** with actionable error.

**Testable rationale:**

- Unit: each engine gate (`execute.intake.gate`, `execute.test.gate`, `execute.repair.limit.gate`, `execute.commit.gate`, verify engine gates, etc.) has table-driven tests for every option.
- Integration: `gate decide` on engine gate returns `CAPABILITY_DENIED`.
- Negative: conflicting evidence (e.g. pass and fail receipts) halts without routing.

---

## 6. Generic task/operation executor (Shape partially done)

**Chosen behavior:** **Partial today; complete in Step 1.** Replace ad-hoc `advance.py` branches with a generic executor that loads declared operations/tasks, validates inputs/outputs against schema, runs host-owned operations deterministically, and dispatches model tasks through the durable agent path. Shape: `shape.intake`, `shape.present`, `shape.record` already have dedicated executors (`intake_executor.py`, `shape_step_executor.py`); `shape.examine` keeps task binding. Step 1 merges these behind one sequence runner and removes operator waits used only for bookkeeping.

**Testable rationale:**

- Integration: Shape E2E (zero-question and multi-round) completes without `operator` waits for receipt/transition.
- Unit: operation YAML from registry executes with mocked host commands; invalid output rejected before state mutation.
- Regression: existing `test_advance.py`, `test_shape_*`, `shape_phase_e2e.feature` stay green.

---

## 7. Remediation findings F1–F9

From the 2026-10-06 implementation review (git history: `implementation-review-remediation.md`). Step 0 status:

| Finding | Status | Pointer | Remaining for workflow-02 |
| --- | --- | --- | --- |
| **F1** — Shape steward boundaries | **Closed** (Shape path) | `c45e713` — host-owned present/record, no operator wait for receipt mechanics | Re-verify after generic executor; Execute/Verify still stubbed |
| **F2** — Answers not re-judged | **Closed** | `c45e713`, `test_examination_round.py` | Keep multi-round acceptance green |
| **F3** — Stub adapter in user mode | **Partial** | `c45e713` — `get_adapter()` fails without config; stub only with `FOUNDRY_ALLOW_STUB_ADAPTER` or pytest | Real provider adapter + bounded `project_context` before Execute agents |
| **F4** — Dispatch not durably staged | **Closed** | `15e1fe9`, `test_agent_dispatch_durable.py` | Extend pattern to all agent nodes in Execute/Verify |
| **F5** — Ledger repair incomplete | **Partial** | `15e1fe9`, `test_run_store_durable.py` | Full replay or transactional checkpoint per plan §2 |
| **F6** — Host socket / ownership | **Closed** | `ad9eb8a`, `test_host_integration.py`, `test_host_paths.py` | Default temp path must pass without short `--basetemp` |
| **F7** — Steward prose in docs/prompts | **Partial** | `c45e713` shape executors; judgment/docs may lag | Regenerate docs after instruction rewrite; audit Execute/Verify prompts |
| **F8** — Idempotency key not bound | **Closed** | `15e1fe9`, `test_host_idempotency_store.py` | No regression on concurrent host clients |
| **F9** — Shape input trimmed | **Closed** | `c45e713`, `test_shape_input_verbatim.py` | Preserve for ticket publication paths |

**Testable rationale:** Step 1 acceptance in remediation plan §§1–3 must pass on default workspace paths before slice 2A starts.

---

## 8. `execute.start` prompt (`/craft-execute`)

**Chosen behavior:** Replace steward slash-command text with **shipped host/CLI language**: frozen plan recorded; user runs `foundry start` (or documented equivalent) to authorize Execute; host records `execute.authorization` evidence and routes to `execute.intake` on `accept`. No instruction to open a new chat or invoke removed craft commands.

**Testable rationale:**

- Generated node page and flow prompt match CLI help.
- Acceptance: `shape_phase_e2e` / `shape_record_gate` paths show updated prompt; `start` advances only after user authorization.
- Negative: prompt string does not contain `/craft-execute`.

---

## 9. Engine gate evidence rules (precedence, loops, findings)

**Chosen behavior:**

1. **Precedence:** examine checks → seal checks → engine resolver reads **latest sealed evidence** for the governing visit; typed findings (schema-id’d) override inferred status.
2. **Execute test gate:** map test receipt exit code and structured result to `pass` | `repair` (and only those unless flow amended).
3. **Verify acceptance gate:** map itemized findings to `pass` | `replan` | `reshape` | `rework_execute` with one finding class driving one route (document priority table in verify slice).
4. **Loops:** use flow `history.count` / `config.limits.*`; exhaustion routes to declared limit gate outcome (halt or terminal failure), not silent accept.
5. **Ownership:** host writes `gate.decided` for engine gates; users only see packets via `status`/`attach`.

**Testable rationale:**

- Table-driven unit tests per gate option and limit boundary (at limit, over limit).
- Integration: forced fail → repair loop → success respects `config.limits.repair`.
- Evidence: each decision event links receipt IDs used in the rule.

---

## 10. `verify.code_quality` `not_applicable` and skip to `verify.code_review`

**Chosen behavior:** When review is disabled (`review-enabled` check fails / config off), `verify.code_quality` seals **`not_applicable`** and routes directly to `verify.code_review` via the existing `not_applicable` connection. **Human code review remains available** unless a separate config flag disables it (default: review gate still active). Quality gate is skipped; quality **gate** node is not visited on skip path.

**Testable rationale:**

- Two configurations tested: review enabled (full quality path) and quality disabled (skip connection taken, code review still reachable).
- Route audit: exactly one outbound connection for `completed` vs `not_applicable`.
- Negative: disabled quality does not auto-`pass` quality gate without `not_applicable` seal.

---

## 11. `deliver.stub` terminal (workflow complete)

**Chosen behavior:** `deliver.stub` is the **workflow terminal**: run status becomes delivered/complete; host emits a short handoff message (branch name, commit SHA when available, verify summary). **No** git push, PR creation, or external delivery automation. User owns subsequent actions. Document in CLI user docs and generated node page.

**Testable rationale:**

- Integration slice 2F: arrival at `deliver.stub` sets terminal status; `attach` shows handoff text.
- Negative: no host command performs `git push`.
- Restart after completion: read-only attach; no duplicate delivery side effects.

---

## Step 0 exit checklist

- [x] Policy decisions recorded (this document)
- [x] Node inventory and check catalog ([node-inventory.md](node-inventory.md))
- [x] Baseline revision and tests captured at Step 0 (`3d4f0fa`, full unit/acceptance green — see git history for `workflow-02-baseline.md`)
- [x] Orchestrator runbook ([remaining-nodes-orchestrator-runbook.md](remaining-nodes-orchestrator-runbook.md))
- [ ] Step 1 implementation (explicitly out of scope for Step 0)

Unresolved `registry:steps/*` refs remain **blocking** for Execute/Verify slices until authored.
