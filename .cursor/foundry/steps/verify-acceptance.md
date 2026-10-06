# verify-acceptance

Host-owned step (workflow-02 slice 2D): publish `verify-findings.json` with deterministic `gate_decision` from sealed state + branch diff, seal implementation-validator receipt, transition to `verify.acceptance.gate`.

Assessment order (non-stub): missing `approved_ac` → `reshape`; missing `final_commit_sha` or unusable diff → `rework_execute`; each non-empty AC line must appear as a case-insensitive substring in the diff or → `replan`; all satisfied → `pass`. Findings include `evidence_ok` and per-item `status`.

`FOUNDRY_VERIFY_ACCEPTANCE_DECISION` is honored only when `FOUNDRY_EXECUTE_STUB=1` (integration tests).
