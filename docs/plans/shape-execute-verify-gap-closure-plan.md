# Shape → Execute → Verify — gap closure plan

Status: **implementation plan** (post independent lifecycle review, 2026-10-06).  
Verdict at review time: **INCOMPLETE** — graph and host executors exist, but a real work item cannot finish Verify without test harness overrides, and Execute does not enforce shaped implementation work.

**Orchestration:** use [orchestrator-brief.md](orchestrator-brief.md) for copy-ready agent commands. Procedure and slice order: [remaining-nodes-orchestrator-runbook.md](remaining-nodes-orchestrator-runbook.md).

**Sources of truth (read before changing contracts):**

| Source | Role |
| --- | --- |
| [.cursor/foundry/flows/factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml) | Node graph, checks, gates, connections |
| [advance.py](../../.cursor/foundry/cli/foundry_cli/engine/advance.py) | Host advancement, build boundary park, waits |
| [execute_step_executor.py](../../.cursor/foundry/cli/foundry_cli/engine/execute_step_executor.py) | Execute intake → commit |
| [verify_step_executor.py](../../.cursor/foundry/cli/foundry_cli/engine/verify_step_executor.py) | Verify intake → complete, acceptance assessment |
| [gates.py](../../.cursor/foundry/cli/foundry_cli/engine/gates.py) | Engine gate resolvers |
| [lifecycle.py](../../.cursor/foundry/cli/foundry_cli/engine/lifecycle.py) | Seal, route, `hold` without connection |
| [node-inventory.md](node-inventory.md) | Per-node boundary status |
| [docs/concepts/graph.md](../concepts/graph.md) | Exact-one route rule |

**Docs refreshed (2026-10-06 cleanup):** [execute-verify-boundary-audit.md](execute-verify-boundary-audit.md) regenerated from `node_capability.audit_rows`; host delivery summarized in [job-host-architecture.md](../concepts/job-host-architecture.md).

---

## A. Implemented lifecycle (baseline for implementers)

Entry: `shape.intake`. Terminal sink: `deliver.stub` (`status: completed`).

```
shape.intake → shape.examine → [shape.examine.gate?] → shape.present → shape.present.gate
  → shape.record → shape.record.gate → execute.start → execute.intake → execute.intake.gate
  → execute.branch → execute.plan → execute.build → execute.test → execute.test.gate
  → [execute.repair.limit.gate → execute.build (loop: repair)]
  → execute.commit → execute.commit.gate → verify.intake → verify.intake.gate
  → verify.acceptance → verify.acceptance.gate → verify.code_quality → verify.code_quality.gate
  → verify.code_review → verify.code_review.gate → verify.complete → verify.complete.gate → deliver.stub
```

Feedback edges (must stay test-covered): acceptance `replan` → `execute.plan`, `reshape` / code_review `reshape` → `shape.intake`, `rework_execute` → `execute.intake`, quality/review `repair` → `execute.repair.limit.gate`.

**What already works (with stubs):** unit test `test_full_path_reaches_deliver_stub_with_handoff` in [test_workflow_slices_2c_2f.py](../../.cursor/foundry/cli/tests/unit/test_workflow_slices_2c_2f.py) — requires `FOUNDRY_EXECUTE_STUB=1` and `FOUNDRY_VERIFY_ACCEPTANCE_DECISION=pass`. Shape acceptance [shape_phase_e2e.feature](../../.cursor/foundry/cli/tests/acceptance/features/shape_phase_e2e.feature) reaches `execute.start` via manual steward steps for present/record (host auto path also exists in `advance.py`).

---

## B. Phase contracts (Inputs → Work → Outputs → Gate → Transition)

Use these as slice acceptance checklists. “Gate” is user or engine per flow `decider`.

### Shape

| Node | Inputs | Work (runtime today) | Outputs | Gate | Next |
| --- | --- | --- | --- | --- | --- |
| `shape.intake` | `work_prompt`, manifest | Host `run_shape_intake_complete` or steward manual path | ticket, receipts | — | `shape.examine` |
| `shape.examine` | ticket | Agent task + host seal on accepted result | agent receipt, state | User if open questions | `shape.present` or gate |
| `shape.present` | `draft_ac` | Host or steward publish | presentation, `presented_ac` | User accept/reject | `shape.record` or `shape.examine` |
| `shape.record` | `presented_ac` | Host freeze plan + `approved_ac` | `plan.md`, digests | — | `shape.record.gate` |
| `shape.record.gate` | plan, AC | User presentation (instructions) | decision only | User accept/**hold** | `execute.start` or **no route** |
| `execute.start` | sealed record | `foundry start` + authorization event | — | User accept | `execute.intake` |

### Execute

| Node | Inputs | Work (runtime today) | Outputs | Gate | Next |
| --- | --- | --- | --- | --- | --- |
| `execute.intake` | frozen plan, AC | Host validation + intake receipt | receipts | Engine pass | `execute.branch` |
| `execute.branch` | slug | Git feature branch | branch state | — | `execute.plan` |
| `execute.plan` | plan | Minimal graph + execute brief | artifacts | — | `execute.build` |
| `execute.build` | graph, AC | **Host stub/manifest build only**; one-step **park** after plan | builder receipt | — | `execute.test` |
| `execute.test` | verification policy | Host runs test commands | repairer receipt | Engine pass/repair | commit or repair loop |
| `execute.commit` | branch | Git commit (empty allowed in stub) | `final_commit_sha` | Engine pass | `verify.intake` |

### Verify

| Node | Inputs | Work (runtime today) | Outputs | Gate | Next |
| --- | --- | --- | --- | --- | --- |
| `verify.intake` | SHA, branch, plan | Diff artifact + context validation | intake receipt | Engine pass | `verify.acceptance` |
| `verify.acceptance` | AC, diff, test exit code | Host `_assess_acceptance` → findings JSON | `verify-findings` | Engine maps decision | quality or feedback |
| `verify.code_quality` | manifest / stub | Command evidence | receipt | Engine pass/repair | review or repair |
| `verify.code_review` | diff, findings | Host stub notes packet | notes | **User** accept/reject/reshape | complete or loops |
| `verify.complete` | — | Host `verified_at` | state | User accept | `deliver.stub` |

---

## C. Findings → work items

Each item includes **severity**, **evidence**, **scenario that exposes it**, and **implementation intent**.

### P0 — Critical (incorrect state or bypass of required work)

#### G1 — Verify acceptance cannot `pass` on the default path

| | |
| --- | --- |
| **Evidence** | [verify_step_executor.py](../../.cursor/foundry/cli/foundry_cli/engine/verify_step_executor.py) `_assess_acceptance`: when tests pass, returns `replan` with all items `not_verified` and `evidence_ok: false`. Pass only via `FOUNDRY_VERIFY_ACCEPTANCE_DECISION=pass` when `FOUNDRY_EXECUTE_STUB=1`. Engine gate requires `evidence_ok is True` for decision `pass` ([gates.py](../../.cursor/foundry/cli/foundry_cli/engine/gates.py) `_verify_acceptance_gate_decision`). |
| **Scenario** | Fresh workspace: complete Shape → Execute with real manifest tests (no stub env). Advance through verify.acceptance. Gate never routes `pass`; run cannot reach `deliver.stub` without env override. |
| **Tests today** | [test_verify_evidence.py](../../.cursor/foundry/cli/tests/unit/test_verify_evidence.py) documents non-pass behavior; full path uses monkeypatched `FOUNDRY_VERIFY_ACCEPTANCE_DECISION=pass`. |
| **Fix intent** | Decide ownership: **agent** `implementation-validator` task produces sealed findings schema with per-criterion status + `gate_decision` + `evidence_ok`; **engine gate only validates** schema and routes. Remove production dependence on env override. Document what evidence counts as “met” (tests, manual checklist, diff scope — pick one policy in [workflow-02-step0-decisions.md](workflow-02-step0-decisions.md)). |

#### G2 — `shape.record.gate` `hold` + `run advance` can mis-complete the run

| | |
| --- | --- |
| **Evidence** | Flow option `hold` has no connection ([node-inventory.md](node-inventory.md)). [lifecycle.py](../../.cursor/foundry/cli/foundry_cli/engine/lifecycle.py) seals gate with `connection: null` on `hold`. [advance.py](../../.cursor/foundry/cli/foundry_cli/engine/advance.py) `_boundary_wait_for_visit`: sealed visit with no `connection.taken` sets `snapshot["status"] = "completed"`. |
| **Scenario** | Fixture at `shape.record.gate`: `gate decide --decision hold` (passes [shape_record_gate.feature](../../.cursor/foundry/cli/tests/acceptance/features/shape_record_gate.feature)). Then `run advance`. **Expected:** paused run awaiting user rework. **Observed (review):** risk of global `completed`. |
| **Fix intent** | Choose policy: (a) `hold` → route to `shape.present` with loop label, or (b) dedicated run status / wait kind `on_hold` that **never** maps to `completed` on advance. Add acceptance: hold → advance → status still runnable; user can accept later. |

#### G3 — Execute does not enforce implementation against shaped work

| | |
| --- | --- |
| **Evidence** | Flow: “builders commit via CLI” ([factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml) ~L511). Runtime: [execute-build.md](../../.cursor/foundry/steps/execute-build.md) host runs stub/manifest commands; `execute_build_boundary` only skips one advance ([advance.py](../../.cursor/foundry/cli/foundry_cli/engine/advance.py)). No wait for workspace diff vs execution graph. |
| **Scenario** | Run reaches `execute.build` with zero code changes; stub build/test pass; empty commit; verify intake may still pass with synthetic diff (tests use `_ensure_feature_branch_diff`). Product claim “execute the shaped work” is not enforced. |
| **Fix intent** | Either **narrow the product contract** (host-only command gate + explicit “implementation happens outside Foundry”) and edit flow/worker prose, **or** add agent/operator **wait** at build until receipt proves graph work items addressed (files changed, task result, or checklist). Align `execute.build` lifecycle checks with chosen model. |

### P1 — Major

#### G4 — Worker bindings bypassed on Execute/Verify intake and execute.test

| | |
| --- | --- |
| **Evidence** | Flow `worker:` on `execute.intake`, `verify.intake`, `execute.test`; host writes engine-mode receipts without agent wait. |
| **Scenario** | Steward follows worker prompt; host advance already sealed pass intake — duplicate/conflicting evidence. |
| **Fix intent** | Per node: **host-only** (remove worker from flow) **or** **agent wait** until task result validates, then host seals. No dual paths. |

#### G5 — Blocked execute/verify intake leaves opened visit without recovery contract

| | |
| --- | --- |
| **Evidence** | [execute_step_executor.py](../../.cursor/foundry/cli/foundry_cli/engine/execute_step_executor.py) / [verify_step_executor.py](../../.cursor/foundry/cli/foundry_cli/engine/verify_step_executor.py): `ok: true`, `transitioned: false`, blocked receipt; step never reaches engine gate. |
| **Scenario** | Missing `approved_ac` at execute intake → blocked. User fixes state — no documented `run retry` / re-invoke path; visit may re-run host step on advance (verify behavior in tests). |
| **Fix intent** | Operator wait with `request_ref`, or explicit reopen policy; acceptance test: block → patch state → pass. |

#### G6 — Dual Shape present/record paths (host vs steward manual)

| | |
| --- | --- |
| **Evidence** | Host executors in [shape_step_executor.py](../../.cursor/foundry/cli/foundry_cli/engine/shape_step_executor.py); e2e uses manual transition ([shape_phase_e2e.feature](../../.cursor/foundry/cli/tests/acceptance/features/shape_phase_e2e.feature)). |
| **Scenario** | Host path skips steward two-turn gate UX enforcement; manual path skips host receipt consistency. |
| **Fix intent** | Single canonical path for production; keep manual CLI only for tests or deprecate with policy. |

#### G7 — Documentation contradicts runtime

| | |
| --- | --- |
| **Evidence** | [execute-verify-boundary-audit.md](execute-verify-boundary-audit.md) lists steps unsupported; [node_capability.py](../../.cursor/foundry/cli/foundry_cli/engine/node_capability.py) marks them implemented. |
| **Fix intent** | Regenerate audit from `node_capability.audit_rows`; update phase doc status to “skeleton complete, gap closure in progress”. |

#### G8 — Failure taxonomy collapsed into `halted` / `execution_error`

| | |
| --- | --- |
| **Evidence** | Engine gate failures in [advance.py](../../.cursor/foundry/cli/foundry_cli/engine/advance.py) set `halted` for several codes; blocked intake vs limit exceeded vs missing evidence not distinguished in status API. |
| **Fix intent** | Typed halt reasons on snapshot + `foundry status` / attach; document retry per reason. |

#### G9 — `reverify-within-limit` declared on commit gate; hook parity unclear

| | |
| --- | --- |
| **Evidence** | Flow lifecycle on `execute.commit.gate`; expression support in [routing.py](../../.cursor/foundry/cli/foundry_cli/engine/routing.py); no dedicated hook id in [hooks.py](../../.cursor/foundry/cli/foundry_cli/engine/hooks.py) grep for reverify. |
| **Scenario** | Second verify cycle after rework — limit may not enforce. |
| **Fix intent** | Implement check + test at limit boundary. |

### P2 — Minor / hygiene

- **G10** — Capability label `unsupported` for host-advanced shape steps ([node_capability.py](../../.cursor/foundry/cli/foundry_cli/engine/node_capability.py)) — fix registration or document as audit-only.
- **G11** — Plan docs consolidated under [README.md](README.md) (done).

---

## D. Required test scenarios (lifecycle, not component-only)

Add or extend acceptance/unit tests as each gap closes.

| ID | Scenario | Proves |
| --- | --- | --- |
| T1 | E2E feature: Shape → Execute (manifest) → Verify → `deliver.stub` **without** `FOUNDRY_VERIFY_ACCEPTANCE_DECISION` | G1, G3 |
| T2 | `shape.record.gate` hold → `run advance` → status ≠ erroneous `completed` | G2 |
| T3 | Execute intake blocked → fix `approved_ac`/plan → advance → intake gate pass | G5 |
| T4 | Verify intake blocked (bad SHA) → recovery | G5 |
| T5 | Acceptance findings with `pass` + `evidence_ok: true` from validator task artifact | G1 |
| T6 | Each feedback route once: repair, replan, reshape, rework_execute with artifact/version checks | Graph loops |
| T7 | Repair limit exceeded → halt → `foundry retry` | G8 |
| T8 | Reverify limit on second verify entry | G9 |
| T9 | Build boundary: agent work window (if policy G3 chooses wait) | G3 |
| T10 | Resume after host restart at execute.start, verify gates | Durability |

---

## E. Prioritized implementation slices

Map to [remaining-nodes-orchestrator-runbook.md](remaining-nodes-orchestrator-runbook.md) slices. **Do not start a dependent slice until verifier accepts the prior one.**

| Order | Slice | Closes | Deliverables |
| ---: | --- | --- | --- |
| 1 | **Gap-G2** Hold / run status | G2 | Flow connection or wait; lifecycle + advance fix; T2 |
| 2 | **Gap-G1** Verify acceptance contract | G1 | Validator task or approved host policy; step + gate tests; T1, T5 |
| 3 | **Gap-G3** Execute build contract | G3 | Wait or contract narrow; flow + steps + T9 |
| 4 | **Gap-G5/G8** Blocked intake + halt reasons | G5, G8 | Waits, status fields, retry docs; T3, T4, T7 |
| 5 | **Gap-G4/G6** Single path workers + shape | G4, G6 | Flow cleanup or agent waits; e2e canonical path |
| 6 | **Gap-G7/G9/G10** Docs + limits | G7, G9, G10 | Regenerated audit, reverify hook, inventory |
| 7 | **Integration** | All | T1, T6, T10; update [acceptance README](../../.cursor/foundry/cli/tests/acceptance/README.md) |

---

## F. End state (definition of COMPLETE)

The lifecycle review verdict moves to **COMPLETE** when all of the following hold:

1. A developer can run Shape → Execute → Verify → `deliver.stub` in a **clean workspace** using **manifest commands only** (stubs opt-in for CI speed, not required for pass).
2. Verify acceptance **`pass`** means sealed findings show shaped AC satisfied under the written policy — not env vars.
3. Execute **build** policy matches flow prose (enforced wait **or** honestly host-only scope).
4. **`hold`**, blocked intake, repair/reverify limits, and feedback loops have **tests** in section D and **documented** recovery.
5. Authored docs, generated docs, and `node_capability` audit agree.

---

## G. Plan index

Active plans: [README.md](README.md). Superseded delivery/remediation/extraction plans were archived via git history after promoting content into step 0 decisions, phase docs, and [shape-deterministic-extraction.md](../shape-deterministic-extraction.md).
