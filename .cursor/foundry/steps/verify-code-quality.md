# verify-code-quality

Host-owned step (workflow-02 slice 2E): when `config.review.enabled`, run stub quality commands (`foundry-stub:code_quality` under `FOUNDRY_EXECUTE_STUB`) and publish `code-quality-report.md`. When review is disabled, seal with outcome `not_applicable` and route directly to `verify.code_review`.
