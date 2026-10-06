# verify-acceptance

Host-owned step (workflow-02 slice 2D): publish `verify-findings.json` with deterministic `gate_decision` (default `pass`; override with `FOUNDRY_VERIFY_ACCEPTANCE_DECISION`), seal implementation-validator receipt, transition to `verify.acceptance.gate`.
