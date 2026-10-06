# verify-code-quality

Host-owned step (workflow-02 slice 2E): when `config.review.enabled`, run quality checks and publish `code-quality-report.md`. When review is disabled, seal with outcome `not_applicable` and route directly to `verify.code_review`.

Under `FOUNDRY_EXECUTE_STUB=1`, use stub command `foundry-stub:code_quality` with optional `FOUNDRY_EXECUTE_CODE_QUALITY_EXIT_CODE`. Otherwise run manifest `code_quality` or `lint` via the same helpers as execute build/test; if neither is defined, record a failing command (exit 1) — no fake pass.
