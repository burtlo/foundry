# Implementation flow runtime

**Doc kind:** feature-record  
**Flow:** `implementation` ([registry.yaml](../../.cursor/foundry/flows/implementation/registry.yaml))  
**As-built:** This feature record is the authoritative description of the shipped implementation flow runtime (orchestration, advance, mechanisms, gates, and task dispatch). Historical delivery plans were removed after ship; use git history for prior plan text.

## Summary

The host advances runs through `advance` using a **node runtime profile** per visit, **bound `operations.yaml`** manifests for host and task steps, **declarative engine gate rules**, and a **typed expression evaluator** for flow `when` checks and gate logic. Steward-facing behavior is unchanged at the contract level; orchestration moved from scattered Python node lists into registry packages.

## Advance model

**Entry:** `foundry_cli.engine.advance.advance_run` (exclusive per-run lock, bounded work loop).

**Classification:** `classify_advance_node` delegates to `load_node_runtime_profile` → `AdvanceMode` (`host`, `task`, `git_mechanical`, `gate_user`, `gate_engine`, `unsupported`). See [engine-node-runtime-profile.md](../concepts/engine-node-runtime-profile.md) for field definitions.

| `AdvanceMode` | Dispatch |
|---------------|----------|
| `host` | `dispatch_host_step_advance` → `MechanismRunner` when `operations_ref` is set |
| `git_mechanical` | Host mechanism for steps with `runtime.advance: git_mechanical` |
| `task` | `ensure_agent_request(task_id)`; complete via task YAML `advance.complete_action` (ActionRegistry) |
| `gate_user` | User `gate decide` / authorization |
| `gate_engine` | `resolve_engine_gate_decision` via `gate.rules.yaml` |
| `unsupported` | Operator unsupported wait (post-shape nodes without binding) |

**Profile flags:** `blocked_intake`, `host_only_boundary`, `requires_work_prompt`, `pending_open_questions`, and `terminal` are loaded from each node package `runtime` section (and `terminal` on the node). Work-prompt operator wait copy comes from `operations.yaml` `presentation.work_prompt_wait` when `requires_work_prompt` is set.

**Inventory:** Regenerate [engine-node-runtime-matrix.md](../generated/engine-node-runtime-matrix.md) with `just engine-matrix`. Execute/Verify/Deliver coverage is derived from the implementation flow (`execute_verify_deliver_flow_node_ids` in `node_runtime_matrix.py`); there is no separate Python node-id tuple or boundary-audit markdown. Unsupported-step waits use `node_capability.boundary_status` only.

## Mechanism binding

Each host step (and task steps that declare `operations:`) binds:

```yaml
operations: registry:nodes/<node_id>/operations.yaml
```

in `nodes/<node_id>/node.yaml`. Catalog / `config validate` expects host and task nodes with an operations file to declare this ref.

**Execution:** `MechanismRunner` (`foundry_cli.engine.mechanism_runner`) loads the manifest, evaluates each mechanism step `when:` with `evaluate_when_expression`, and runs registered **actions** (`foundry_cli.engine.actions`, e.g. `visit.intake.complete`, `receipt.seal`, `run.advance.park`). Policy blocks (`policy.admission`, `policy.completion.transition`) are enforced by lifecycle hooks and transition helpers aligned with the manifest.

**Migrated host steps (7a–7d):** `shape.intake`; `execute.intake`, `execute.branch`, `execute.build`, `execute.test`, `execute.commit`; `verify.intake`, `verify.code_quality`, `verify.code_review`, `verify.complete`; `deliver.stub`.

**Judgment / task steps (Step 8):** `shape.examine`, `shape.present`, `shape.record`, `execute.plan`, `verify.acceptance` use generic `ensure_agent_request` and task YAML `accept` predicates; some retain thin Python complete adapters until fully mechanismized.

## Engine gate rules

Engine gates (`decider: engine`) ship `nodes/<gate>/gate.rules.yaml`. Resolution (`foundry_cli.engine.gate_rules` + `gates.resolve_engine_gate_decision`):

1. `lifecycle.on_examine` checks from the gate `node.yaml` must be recorded pass (limit checks use live evaluation when not yet recorded).
2. **Evidence** bindings (`evidence.gate_evidence` in `foundry_cli.engine.evidence`) populate `evidence.<id>` views (receipt, artifact, state).
3. **`derive`** expressions run in order → `derived.<name>`.
4. Ordered **`rules`**: first matching `when` wins → `decision` / `decision_from` or `reject` + message template.

**Gates on rules files:** `execute.intake.gate`, `execute.test.gate`, `execute.repair.limit.gate`, `execute.commit.gate`, `verify.intake.gate`, `verify.acceptance.gate`, `verify.code_quality.gate`.

Expressions in gate rules use `expressions.evaluate_condition` with roots `evidence`, `derived`, `state`, `config`, `history`.

## Expression evaluator

**Shipped:** Track 2 typed evaluator in `foundry_cli.engine.expressions` ([expression-language-backlog.md](../plans/expression-language-backlog.md)).

- `evaluate_when_expression` — flow connection and hook `when` strings (parity: `tests/unit/test_expressions_parity.py` over implementation-flow registry).
- `evaluate_condition` — gate rules and mechanism step `when`.
- **No new** substring matchers in `routing.py`; loop limits stay in `loop_limits.py`.

Normative syntax notes: [expressions.md](../concepts/expressions.md).

## Code map

| Area | Module |
|------|--------|
| Advance loop | `.cursor/foundry/cli/foundry_cli/engine/advance.py` |
| Classification / dispatch | `advance_classifier.py`, `node_runtime_profile.py` |
| Mechanisms | `mechanism_runner.py`, `actions.py` |
| Gates | `gates.py`, `gate_rules.py`, `evidence.py` |
| When / conditions | `expressions.py`, `routing.py` (delegate) |
| Operations load | `foundry_cli/node_operations.py` |
| Flow registry | `.cursor/foundry/flows/implementation/registry.yaml` |

## Test scenario map (T1–T10)

Workflow policy scenarios referenced from unit and acceptance tests. **Canonical** paths use host `run advance` and production gate rules; **stub** paths use env stubs (`FOUNDRY_EXECUTE_*`, fixture helpers) for faster execute/verify slices.

| ID | Intent | Primary evidence | Stub vs canonical |
|----|--------|------------------|-------------------|
| T1 | Shape intake deterministic (no model on happy path) | `shape_intake.feature`, `test_shape_intake_complete.py` | Canonical |
| T2 | Paused/hold run must not auto-complete on advance (G2) | `test_advance.py` | Unit |
| T3 | Blocked execute intake operator wait | `test_rel011_blocked_intake_recovery.py` | Unit |
| T4 | Blocked verify intake recovery | `test_rel011_blocked_intake_recovery.py` | Unit |
| T5 | Durable host advance / storage idempotency | `job_host.feature`, `run_storage.feature` | Acceptance |
| T6 | Shape phase via host advance after create | `shape_canonical_advance.feature` | Canonical |
| T7 | Repair loop limit → halt / retry | `test_rel005_loop_history.py` | Unit |
| T8 | Reverify limit at `execute.commit.gate` | `test_rel005_loop_history.py` | Unit |
| T9 | Execute test gate pass/repair routing | `execute_test_gate.feature`, `test_execute_test_gate.py` | Stub execute common |
| T10 | Full run completes at `deliver.stub` | `test_deliver_stub_handoff.py`, stub helpers | Stub execute/verify; verify acceptance uses adapter path in production |
| T11 | Operator stack: HTTP bridge + host + shape advance | `test_operator_integration_smoke.py`, `python -m foundry_cli.operator_integration_smoke` | **Canonical** judgment via `FOUNDRY_AGENT_HTTP_URL` (smoke mocks Cursor SDK by default); host `run advance` through `shape.present.gate` |

Acceptance index: [tests/acceptance/README.md](../../.cursor/foundry/cli/tests/acceptance/README.md).

**Operator judgment path (production-shaped):** job host with `FOUNDRY_AGENT_ADAPTER=http` and `FOUNDRY_AGENT_HTTP_URL` pointing at `foundry bridge start`; optional `host start --auto-advance` for agent waits. See [judgment-bridge.md](judgment-bridge.md) and [operator runbook § integration smoke](../operator-runbook.md#integration-smoke). CLI-only stub adapter (`FOUNDRY_AGENT_ADAPTER=stub`) remains valid for fast unit/acceptance slices.

## Open gaps (not this record)

- **Checkpoint-based ledger recovery** is shipped (`ledger_replay.py`, `test_ledger_store.py`). Optional **full event reducers** that rebuild visit/state from ledger alone without checkpoints remain deferred, not blocking operator use.
- **Operator integration:** shipped — [judgment bridge](judgment-bridge.md), host client timeouts ([run-advance.md](../cli/run-advance.md)), [host auto-advance](host-auto-advance.md), [host TUI protocol](host-tui-protocol.md), [Textual TUI](foundry-tui.md), [integration smoke](../operator-runbook.md#integration-smoke). Out of scope: [operator runbook § out of scope](../operator-runbook.md#out-of-scope-current-operator-stack).
