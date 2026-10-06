# verify-intake

Host-owned step (workflow-02 slice 2D): capture branch diff artifact, validate execute context (`final_commit_sha` resolves to a commit, is on `feature_branch` and matches branch tip, usable `default...feature` diff), seal verify intake + agent receipts.

On validation failure, intake receipt status is `blocked`, assessment lists concrete findings, and the visit does **not** transition (mirrors `execute.intake`). On success, transition to `verify.intake.gate`.

Diff is unusable when it starts with `# branch diff unavailable` or `# git diff failed`, or is only `# (no diff vs default branch)`.
