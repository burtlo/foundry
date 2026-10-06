# verify-acceptance

Host-owned step (workflow-02 slice 2D): publish `verify-findings.json` with deterministic `gate_decision` from sealed execute context, seal implementation-validator receipt, transition to `verify.acceptance.gate`.

Assessment order (non-stub): missing `approved_ac` → `reshape`; missing `final_commit_sha`, failed/missing execute tests (`last_test_exit_code` ≠ 0), or unusable diff → `rework_execute`; when automated tests passed but behavioral AC are not machine-verified → `replan` with per-item `status: not_verified` and `evidence_ok: false`. The host does **not** treat acceptance-criteria text appearing in the branch diff as proof of behavior.

`gate_decision: pass` with `evidence_ok: true` is only produced when `FOUNDRY_EXECUTE_STUB=1` and `FOUNDRY_VERIFY_ACCEPTANCE_DECISION=pass` (integration tests). Production acceptance pass requires future bounded validator evidence, not diff substring checks.
