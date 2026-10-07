# Release integration plan

Status: **done** (REL-019) — implementation-flow release **COMPLETE** per gap plan §F.  
**Parent:** [release-charter.md](release-charter.md) wave **R-7**.  
**Definition of COMPLETE:** [shape-execute-verify-gap-closure-plan.md](shape-execute-verify-gap-closure-plan.md) §F.  
**Scenarios:** same doc §D (**T1**–**T10**).

## Scope

| ID | Scenario | Depends on |
| --- | --- | --- |
| T1 | E2E Shape → Execute (manifest) → Verify → `deliver.stub` without verify env override | **G1**, **G3**, [agent-adapter-integration-plan.md](agent-adapter-integration-plan.md) |
| T2 | `shape.record.gate` hold → advance → status not erroneous `completed` | **G2** |
| T3–T4 | Blocked execute/verify intake → recovery | **G5** |
| T5 | Acceptance findings `pass` + `evidence_ok: true` from validator artifact | **G1** |
| T6 | Each feedback route once (repair, replan, reshape, rework_execute) | Graph + gates |
| T7 | Repair limit → halt → `retry` | **G8** |
| T8 | Reverify limit on second verify entry | **G9** |
| T9 | Build boundary per G3 policy | **G3** |
| T10 | Resume after host restart at execute.start, verify gates | Host durability |

## Deliverables

- [acceptance README](../../.cursor/foundry/cli/tests/acceptance/README.md) updated for canonical (non-stub-default) path
- [node-inventory.md](node-inventory.md) + [execute-verify-boundary-audit.md](execute-verify-boundary-audit.md) regenerated
- [README.md](README.md) release charter status row set to **COMPLETE**

## Evidence gates

[orchestrator-brief.md](orchestrator-brief.md) — full `dev unit`, `dev acceptance`, `dev docs`, clean git diff on `docs` and `.cursor/foundry`.

## Test scenario coverage (T1–T10)

Honest map to tests and features after REL-001–REL-018. **Stub** = `FOUNDRY_EXECUTE_STUB` / default pytest `conftest` verify pass env; **canonical** = host/agent path without verify-decision override for production adapter policy.

| ID | Coverage | Primary evidence |
| --- | --- | --- |
| **T1** | **Partial (stub E2E)** | Unit `test_deliver_stub_complete.py`, acceptance `test_deliver_stub_handoff.py` — full path to `deliver.stub` with stub execute/verify. Adapter policy: `test_http_agent_adapter.py` (`test_stub_verify_acceptance_pass_without_execute_stub_override`). No single acceptance feature for manifest-only Shape→Verify without stub env. |
| **T2** | **Canonical** | Acceptance `shape_record_gate.feature` (hold → advance → `running`); unit `test_advance.py` (`test_advance_after_record_gate_hold_keeps_running`). |
| **T3** | **Canonical** | Unit `test_rel011_blocked_intake_recovery.py` (`test_execute_intake_blocked_then_recovery_t3`). |
| **T4** | **Canonical** | Unit `test_rel011_blocked_intake_recovery.py` (`test_verify_intake_blocked_then_recovery_t4`). |
| **T5** | **Canonical (unit)** | `test_verify_evidence.py` — sealed findings `pass` + `evidence_ok`; gate resolver tests; agent `implementation-validator` binding covered in render/adapter tests. |
| **T6** | **Partial (unit/graph)** | Feedback decisions in `test_verify_evidence.py`, `test_engine_gates.py`, flow helper/catalog loop tests — not one acceptance scenario per route end-to-end. |
| **T7** | **Canonical** | `test_rel005_loop_history.py` — repair limit exceeded → halt → `retry`. |
| **T8** | **Canonical** | `test_rel005_loop_history.py`, `test_engine_gates.py` — reverify limit fail-closed at resolver. |
| **T9** | **Canonical (unit)** | `test_execute_build_complete.py` — `execute_build_boundary` / repair reentry park; `run_context.feature` markdown asserts boundary reason. |
| **T10** | **Partial** | Acceptance `run_storage.feature` + unit `test_host_idempotency_store.py` — host idempotency across restart; not dedicated resume-at-`execute.start` / verify-gate fixtures. |

**Canonical Shape advance (G6):** acceptance `shape_canonical_advance.feature` (REL-013).
