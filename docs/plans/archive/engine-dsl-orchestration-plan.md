# Engine DSL orchestration plan

Status: **done** (orchestration shipped through Step 10 / 7–9; Step 11–FINAL remain as follow-ups).  
**As-built:** [implementation-flow-runtime.md](../../features/implementation-flow-runtime.md).  
**Parent context:** [step1-runtime-prerequisites-plan.md](../step1-runtime-prerequisites-plan.md) (item 5 generic executor), [expression-language-backlog.md](../expression-language-backlog.md), [job-host-architecture.md](../../concepts/job-host-architecture.md) (advance contract).  
**North star:** `advance` runs a thin loop; **node packages** (flow registry + bound `operations.yaml` + tasks) declare orchestration; Python provides **registered actions** (git, receipts, subprocess, schema validation) and **kernels** (lifecycle, expressions, evidence, agent transport).

## Problem statement (what moves out of code)

| In code today | Should live in configuration |
|---------------|------------------------------|
| `advance_classifier` / `node_capability` node ID sets and handler maps | Node `runtime` profile + bound `operations.yaml` |
| `*_step_executor.run_*_complete` scripts | Executable `mechanism:` steps |
| `gates.py` `_ENGINE_RESOLVERS` per gate | Declarative gate evidence + rules on gate nodes |
| `routing.py` substring `when` matching | Typed expression evaluator over `registry.yaml` |
| `agent/dispatch.ensure_*` copies | Generic `ensure_agent_request(task_id)` + task YAML |
| `advance.py` special cases (e.g. execute.build park) | Mechanism `when:` / policy on node package |
| `transition_policy.py` one-off rules | `operations.yaml` `policy.completion.transition` |

**Stays in code:** ledger I/O, lifecycle spine (`lifecycle.py`), hook runner shell, action plugins, agent adapter, domain transforms (e.g. `examination_state`).

## Orchestrator playbook

### Roles

| Role | Responsibility |
|------|----------------|
| **Orchestrator** | Runs steps in order; does not implement; spawns one **Implementer** subagent per step; spawns **Verifier** after each step (or after a **verification batch**); blocks merge until verifier passes. |
| **Implementer subagent** | Delivers exactly one step’s deliverables; no scope creep into later steps; documents any contract change in step PR description. |
| **Verifier subagent** | Read-only: run listed tests, check acceptance criteria, confirm no duplicate registries reintroduced; report pass/fail with evidence. |

### Subagent launch template (implementer)

```text
Full Repository Path: /Users/lynnfrank/src/foundry
Plan: docs/plans/archive/engine-dsl-orchestration-plan.md
Step: <STEP-ID> — <title>
Goal: <copy "Supports larger goal" from step>
Deliverables: <copy from step>
Out of scope: <later steps>
Constraints:
  - Minimize behavior change unless step explicitly migrates a node.
  - Do not add new routing.py substring matchers (expression backlog).
  - Prefer extending lifecycle/hooks over new advance branches.
Run after implement: <commands from step>
```

### Subagent launch template (verifier)

```text
Full Repository Path: /Users/lynnfrank/src/foundry
Plan: docs/plans/archive/engine-dsl-orchestration-plan.md
Verify: Step <STEP-ID> completion
Checklist: <copy "Verifier checklist" from step>
Run: <test commands>
Report: PASS/FAIL per checklist item with command output summary.
```

### Parallelism

- **Sequential:** Steps 0 → 1 → 2 must complete before mechanism work (5–8).
- **Parallel allowed:** Step 3 (evidence) and Step 4 (expressions) after Step 2; merge both before Step 10 (gate rules).
- **Batched migration (7a–7d):** One implementer per batch; batches are sequential.

### Verification batches

| After step(s) | Verifier focus |
|---------------|----------------|
| 2 | Classification parity; no behavior change |
| 4 | Expression parity vs old `routing.py` for implementation flow |
| 7 (pilot) | `shape.intake` + intake tests only |
| 8 (full) | T1–T10 / acceptance features per implementation-flow-runtime |
| 11 | Advance/classifier line count down; no node ID dicts in `advance.py` |
| **FINAL** | Full CLI unit + acceptance; drift CI green |

---

## Step 0 — Node runtime matrix (inventory)

**Supports larger goal:** Makes drift visible; every later step closes rows in the matrix.

**Work:**

1. Add a script or `foundry doc`/catalog target that emits **node runtime matrix** (CSV or markdown): for each implementation-flow node: `kind`, `decider`, hooks used, `allow.cli`, task file exists, `operations.yaml` exists, bound in `node.yaml`, Python complete fn (grep), advance_classifier entry, gate resolver, `node_capability` status.
2. Check in generated artifact under `docs/generated/` (or test-only fixture) and wire `just` / CI **drift check** (optional in this step; required by Step 6).

**Deliverables:**

- `docs/generated/engine-node-runtime-matrix.md` (or equivalent generator + doc)
- Short README in plan or `docs/generated/README.md` on how to regenerate

**Verifier checklist:**

- [ ] Matrix lists all nodes from `flows/implementation/registry.yaml`
- [ ] Regenerate command documented
- [ ] No production behavior change

**Tests:** Generator unit test or smoke `just` target.

---

## Step 1 — Runtime profile schema and loader

**Supports larger goal:** Single API for advance, capability audit, and steward context—replaces triple node-ID lists.

**Work:**

1. Define **NodeRuntimeProfile** (dataclass or typed dict): fields such as `advance_mode` (`host` | `task` | `git_mechanical` | `gate_user` | `gate_engine` | `manual` | `unsupported`), `operations_ref`, `task_id`, `blocked_intake`, `host_only_boundary`, `engine_gate_resolver` (legacy id until Step 10).
2. Implement `load_node_runtime_profile(node_id, flow, foundry_bundle) -> NodeRuntimeProfile` using `node.yaml`, catalog index, filesystem (`tasks/`, `nodes/*/operations.yaml`).
3. Document schema in plan appendix or `docs/concepts/engine-node-runtime-profile.md` (short).

**Deliverables:**

- New module e.g. `foundry_cli/engine/node_runtime_profile.py`
- Unit tests: profile for `shape.intake`, `shape.examine`, `execute.build`, `execute.test.gate`

**Dependencies:** Step 0 (optional but helps validate).

**Verifier checklist:**

- [ ] Profile for every implementation node matches current implicit behavior in `classify_advance_node`
- [ ] No callers switched yet (loader only)

**Tests:** `pytest .cursor/foundry/cli/tests/unit/test_node_runtime_profile.py`

---

## Step 2 — Unify classification (parity refactor) — **done**

**Supports larger goal:** `advance_classifier`, `node_capability`, and `advance` fallbacks use **only** `NodeRuntimeProfile`; delete duplicated frozensets.

**Work:**

1. Refactor `classify_advance_node` to delegate to profile (keep enum `AdvanceNodeClass` for now).
2. Refactor `node_capability.boundary_status` and related helpers to use profile.
3. Remove or shrink `_HOST_IMPLEMENTED_STEP_NODES`, `TASK_BOUND_STEP_NODE_IDS`, `GIT_MECHANICAL_STEP_NODE_IDS`, `EXECUTE_VERIFY_DELIVER_NODE_IDS` from `node_capability.py` where redundant.
4. Keep handler **maps** in `advance_classifier.py` temporarily (Step 11 removes them).

**Deliverables:**

- Behavior-neutral refactor; existing tests green

**Dependencies:** Step 1.

**Verifier checklist:**

- [x] `test_advance_classifier.py`, `test_advance.py`, node capability tests pass unchanged
- [x] Grep shows no second copy of host/task node lists in `node_capability.py` (except deprecated aliases if needed one release)

**Tests:** `pytest .cursor/foundry/cli/tests/unit/test_advance_classifier.py .cursor/foundry/cli/tests/unit/test_advance.py` + capability tests

---

## Step 3 — Evidence read model — **done**

**Supports larger goal:** Gate rules and mechanisms reference evidence declaratively; stop copying ledger→file walks.

**Work:**

1. Add `foundry_cli/engine/evidence.py`: primitives `load_linked_receipt(snapshot, visit_id, schema)`, `sealed_step_visit_id(snapshot, node_id)`, `agent_receipt_summary`, `intake_receipt_summary` (move from `gates.py` / `hooks.py` without behavior change).
2. Switch `gates.py` resolvers and `hooks._load_agent_receipt_for_visit` to import evidence module (thin wrappers OK).

**Deliverables:**

- `evidence.py` + tests
- Reduced duplication in `gates.py` (line count down, behavior same)

**Dependencies:** Step 2 (optional).

**Verifier checklist:**

- [x] All gate unit tests pass
- [x] No new public steward behavior change

**Tests:** Gate-related unit tests; `test_hooks.py` if present

---

## Step 4 — Expression evaluator (parity track) — **done**

**Supports larger goal:** `registry.yaml` `when` and checks are truth; end `routing.py` substring growth.

**Work:**

1. Follow [expression-language-backlog.md](expression-language-backlog.md) **track 2 (typed evaluator)** OR documented **track 1** freeze: implement evaluator that passes **parity suite** for all `when` expressions used in implementation flow connections and flow checks.
2. Route `evaluate_when_expression` through new evaluator; keep old implementation behind flag until parity proven, then delete branches.
3. Do **not** add new `if "substring" in expr` branches.

**Deliverables:**

- `foundry_cli/engine/expressions.py` (or extend `routing.py` with clear evaluator class)
- Parity tests: table-driven from `registry.yaml` extracted expressions

**Dependencies:** Step 2 recommended.

**Verifier checklist:**

- [x] Parity tests 100% for implementation flow
- [x] `test_rel005_loop_history`, routing-related tests pass
- [x] expression-language backlog updated (track chosen)

**Tests:** New `test_expressions_parity.py` + existing routing/hook tests

**Parallel with:** Step 3.

---

## Step 5 — Action registry and mechanism runner (skeleton)

**Supports larger goal:** Executable `operations.yaml` instead of `run_*_complete` monoliths.

**Work:**

1. Define **action registry**: map `action` string → callable (`visit.intake.complete`, `receipt.seal`, `artifact.publish`, `visit.transition`, `subprocess`, `visit.state_patch`, `run.advance.park`, etc.).
2. Implement **MechanismRunner**: load `operations.yaml` via `node_operations.load_operations`, evaluate step `when:` (Step 4 evaluator), execute steps in order, return structured outcome (`ok`, `wait`, `transitioned`, …).
3. Runner does **not** wire into advance yet; unit tests with fixture operations and in-memory snapshot.

**Deliverables:**

- `foundry_cli/engine/mechanism_runner.py`
- `foundry_cli/engine/actions/` or `actions.py` registry
- Tests with minimal fake operations manifest

**Dependencies:** Steps 1, 4 (for `when` on mechanism steps).

**Verifier checklist:**

- [ ] Runner executes a 3-step fake mechanism in tests
- [ ] No advance behavior change yet

**Tests:** `test_mechanism_runner.py`

---

## Step 6 — Bind operations in node packages + validation — **done**

**Supports larger goal:** `operations.yaml` is no longer “author-only”; catalog and CLI validate bindings.

**Work:**

1. Add `operations: registry:nodes/<id>/operations.yaml` to each node `node.yaml` that has an operations file (or document generation from catalog index).
2. Extend catalog validation / `foundry config validate` (or unit test) to require: host/task nodes have `operations` + `runtime.advance` (from Step 1 schema); judgment nodes have `tasks/<id>.yaml`.
3. Update Step 0 matrix generator to fail CI if Python-only node (complete fn in code but no bound operations) for migrated tiers (start with **warn**, tighten in Step 8).

**Deliverables:**

- Updated `.cursor/foundry/nodes/*/node.yaml` (or index-only if that’s the bundle contract)
- Validation tests

**Dependencies:** Steps 1, 5.

**Verifier checklist:**

- [ ] Every node with existing `operations.yaml` is bound
- [ ] Validate command fails on deliberate fixture break

**Tests:** `test_catalog.py` / registry validation tests

---

## Step 7 — Mechanism migration (host steps, batched)

**Supports larger goal:** Remove per-node complete functions from advance path incrementally.

Run **four implementer subagents sequentially** (7a → 7b → 7c → 7d). Each batch: wire `MechanismRunner` from advance for those nodes, shrink Python complete to action implementations, keep ledger events identical.

| Batch | Nodes | Primary legacy module |
|-------|--------|------------------------|
| **7a** | `shape.intake` | `intake_executor.py` |
| **7b** | `execute.intake`, `verify.intake` | `execute_step_executor`, `verify_step_executor` |
| **7c** | `execute.branch`, `execute.build`, `execute.test`, `execute.commit` | `execute_step_executor.py` |
| **7d** | `verify.code_quality`, `verify.code_review`, `verify.complete`, `deliver.stub` | `verify_step_executor.py` |

**Per-batch work:**

1. Align `operations.yaml` mechanism with actual steps (remove `invokes: advance._…` prose; use real actions).
2. Advance host path: `dispatch_host_step_advance` → `MechanismRunner` for batch nodes.
3. Move execute.build **park** from `advance.py` to mechanism/policy (Step 11 may finish cleanup).
4. Delete or deprecate unused `run_*_complete` entry points only when advance + CLI commands use runner.

**Dependencies:** Steps 5, 6.

**Verifier checklist (per batch):**

- [ ] Listed unit tests for batch pass
- [ ] Acceptance features touching batch pass (see batch table in implementation-flow test map)
- [ ] Matrix row shows `runtime: mechanism` for migrated nodes

**Tests (examples):**

- 7a: `test_intake_executor.py`, shape intake acceptance
- 7b: `test_execute_intake.py`, `test_rel011_blocked_intake_recovery.py`, verify intake tests
- 7c: execute build/test/commit unit + repair limit tests
- 7d: verify + `test_deliver_stub_handoff.py`

---

## Step 8 — Judgment steps and generic agent path

**Supports larger goal:** Task-bound advance without per-node lambdas in `advance_classifier`.

**Work:**

1. Implement `ensure_agent_request(snapshot, visit, flow, task_id)` replacing duplicated `ensure_shape_*` / `ensure_execute_plan_request` / `ensure_verify_acceptance_request`.
2. Task YAML: document `accept` rule (`task_result` vs `verdict == PROCEED`); implement generic predicates.
3. Wire task-bound boundary wait + advance via profile `task_id` + shared complete hooks (`shape_step_executor` remains domain actions invoked by mechanism or thin adapter).
4. Nodes: `shape.examine`, `shape.present`, `shape.record`, `execute.plan`, `verify.acceptance`.

**Deliverables:**

- Slim `agent/dispatch.py`
- `advance_classifier` task dicts shrink to generic dispatch

**Dependencies:** Steps 2, 5 (runner for complete steps where applicable).

**Verifier checklist:**

- [ ] `test_shape_examine_complete.py`, agent dispatch tests, `shape_canonical_advance.feature` (or equivalent) pass
- [ ] No new per-task `ensure_*` functions without RFC

**Tests:** Shape + agent unit tests; acceptance shape phase E2E

---

## Step 9 — Transition and blocked-intake policy from config

**Supports larger goal:** Remove `transition_policy.py` and scattered `node_id ==` intake rules.
**Status:** done (2026-10-07)

**Work:**

1. Encode blocked transition rules in node `operations.yaml` `policy.completion.transition` (shape + execute + verify intake).
2. Engine enforces policy in one place (`transition_visit` or mechanism post-condition).
3. Remove `HOST_ONLY_STEP_NODE_IDS` / hardcoded lists from `blocked_intake.py` where profile flags suffice.

**Dependencies:** Steps 7a–7b.

**Verifier checklist:**

- [ ] `transition_policy` module deleted or re-exports only
- [ ] REL-011 / blocked intake tests pass

---

## Step 10 — Declarative engine gate decisions — **done**

**Supports larger goal:** Gate `node.yaml` + rules file drive `pass`/`repair`/…; shrink `gates.py` resolvers.

**Work:**

1. Introduce gate rules asset (e.g. `nodes/<gate>/gate.rules.yaml` or section in `operations.yaml`): evidence source (sealed step, schema), ordered rules mapping expression → `decision` + `rule_id`.
2. Implement `resolve_engine_gate_decision` via rules engine + evidence module (Step 3) + expressions (Step 4).
3. Migrate resolvers one gate at a time: `execute.intake.gate`, `execute.test.gate`, `execute.repair.limit.gate`, `execute.commit.gate`, `verify.intake.gate`, `verify.acceptance.gate`, `verify.code_quality.gate`.
4. Delete `_ENGINE_RESOLVERS` and `_GATE_EXAMINE_CHECKS` when `on_examine` comes only from `node.yaml` + recorded checks.

**Dependencies:** Steps 3, 4, 7 (host evidence producers).

**Verifier checklist:**

- [x] Gate behavior unchanged on unit fixtures
- [x] `gate_examine_check_ids()` derived from node yaml or removed
- [x] `gates.py` significantly smaller

**Tests:** Existing gate unit tests; execute/verify gate acceptance features

---

## Step 11 — Thin advance loop

**Supports larger goal:** `advance.py` only budgets, waits, calls kernels—not flow knowledge.

**Work:**

1. Remove `advance_classifier` handler maps (`_HOST_ADVANCE`, `_TASK_BOUND_*`, …); advance calls `MechanismRunner` + generic task dispatch + `resolve_engine_gate`.
2. Remove execute.build park state from `advance.py` if not already in mechanism.
3. Collapse `_boundary_wait_for_visit` to profile-driven wait kinds.
4. Deprecate `advance_classifier.py` or reduce to thin facade.

**Dependencies:** Steps 7, 8, 10.

**Verifier checklist:**

- [ ] `advance.py` has no implementation-flow node constants (grep)
- [ ] `job_host.feature`, `test_advance.py` pass

---

## Step 12 — Documentation and feature record — **done**

**Supports larger goal:** Shipped behavior documented; step1 item 5 closed.

**Work:**

1. Update or create `docs/features/implementation-flow-runtime.md` (if missing, restore from concepts pointer): advance model, mechanism binding, gate rules, expression evaluator.
2. Link As-built from this plan; set plan status **done** or move to archive per [docs-plans-vs-features](.cursor/rules/docs-plans-vs-features.mdc).
3. Update [step1-runtime-prerequisites-plan.md](step1-runtime-prerequisites-plan.md) item 5 to **Delivered** with evidence.
4. Refresh `operations.yaml` headers (remove “author-only” where bound).

**Dependencies:** Step 11.

**Verifier checklist:**

- [ ] Feature record matches code
- [ ] plans/README.md updated

---

## Step FINAL — Independent verification subagent

**Supports larger goal:** Orchestrator sign-off before merge to main.

**Scope:** Read-only full regression + architecture guards.

**Verifier checklist:**

- [ ] `pytest` unit suite under `.cursor/foundry/cli/tests/unit/` green (or documented `just` equivalent)
- [ ] Acceptance: `shape_phase_e2e`, `shape_canonical_advance`, `job_host`, execute/verify critical paths
- [ ] **Drift:** Node runtime matrix shows no “Python-only host step” without waived flag
- [ ] **grep guards:** No new entries in `_HOST_ADVANCE`-style dicts; `routing.py` substring count not increased (or evaluator-only)
- [ ] Line-count budget: `advance_classifier.py` < 200 lines OR deleted; `gates.py` resolvers replaced by rules (target < 400 lines total file)
- [ ] `foundry config validate` (or equivalent) passes on foundry repo workspace

**Report format:** Table PASS/FAIL per item; blockers with file:line; recommended follow-ups (deferred-contract-slices only if explicitly out of scope).

---

## Appendix A — Key files (implementers)

| Area | Path |
|------|------|
| Advance loop | `.cursor/foundry/cli/foundry_cli/engine/advance.py` |
| Classification (legacy) | `.cursor/foundry/cli/foundry_cli/engine/advance_classifier.py` |
| Step scripts | `execute_step_executor.py`, `verify_step_executor.py`, `shape_step_executor.py`, `intake_executor.py` |
| Gates | `.cursor/foundry/cli/foundry_cli/engine/gates.py` |
| Routing / when | `.cursor/foundry/cli/foundry_cli/engine/routing.py` |
| Lifecycle | `.cursor/foundry/cli/foundry_cli/engine/lifecycle.py` |
| Operations manifests | `.cursor/foundry/nodes/*/operations.yaml` |
| Flow registry | `.cursor/foundry/flows/implementation/registry.yaml` |
| Tasks | `.cursor/foundry/tasks/*.yaml` |

## Appendix B — Suggested REL / branch naming

- `REL-DSL-00` inventory, `REL-DSL-01` profile, … `REL-DSL-11` thin advance
- One PR per step (or per batch 7a–7d) for reviewability

## Appendix C — Out of scope (defer)

- Full transactional materialized-state replay (step1 F5)
- TUI/web host
- New workflow nodes or connection graph changes unrelated to migration
- Optional slices in [deferred-contract-slices.md](deferred-contract-slices.md)

---

## Progress tracker

| Step | Status | PR / notes |
|------|--------|------------|
| 0 | done | `foundry dev engine-matrix` / `just engine-matrix`; matrix at `docs/generated/engine-node-runtime-matrix.md` |
| 1 | done | `node_runtime_profile.py`, `docs/concepts/engine-node-runtime-profile.md` |
| 2 | done | profile-driven classification parity |
| 3 | done | `evidence.py`; gate/hook consumers (tracker was stale) |
| 4 | done | `expressions.py`, `test_expressions_parity.py` |
| 5 | done | `engine/actions.py`, `engine/mechanism_runner.py`, `test_mechanism_runner.py` |
| 6 | done | operations/runtime bindings + node contract validation + matrix warnings |
| 7a | done | shape.intake host advance now dispatches through `MechanismRunner` using `visit.intake.complete` action; operations mechanism aligned to executable action steps. |
| 7b | done | execute.intake + verify.intake host advance now dispatches through `MechanismRunner` using `visit.intake.complete`; operations mechanisms aligned to executable action step delegates for ledger parity. |
| 7c | done | execute.branch (`git_mechanical`) + execute.build/test/commit now dispatch via `MechanismRunner`; execute step operations aligned to real execute-complete actions; execute.build boundary park moved from `advance.py` into execute mechanism action/policy path. |
| 7d | done | verify.code_quality/review/complete + deliver.stub now dispatch through `MechanismRunner` with deterministic complete actions and bound operations manifests. |
| 8 | done | Generic `ensure_agent_request` + task YAML `accept` predicates + profile-driven task dispatch for shape/execution/verify judgment nodes. |
| 9 | partial | `transition_policy.py` reads `operations.yaml` policy; module retained |
| 10 | done | All 7 engine gates decide via `nodes/<gate>/gate.rules.yaml` (`engine/gate_rules.py` + `evidence.gate_evidence` + `expressions.evaluate_condition`); `_ENGINE_RESOLVERS`, `_GATE_EXAMINE_CHECKS`, `_LIMIT_CHECK_FAIL_CODES` deleted; examine check ids from gate `node.yaml`; `gates.py` 845 → ~430 lines; `test_gate_rules.py`. |
| 11 | done | [engine-dsl-follow-up-plan.md](engine-dsl-follow-up-plan.md) (runtime.advance, thin advance) |
| 12 | done | `docs/features/implementation-flow-runtime.md`; plan archived |
| FINAL | not started | |
