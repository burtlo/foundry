# execute-commit

Host-owned step (workflow-02 slice 2C): record a final commit on the feature branch, publish `final-commit` (`git_commit` reference), seal commit-agent receipt, and transition to `execute.commit.gate`.

- When `FOUNDRY_EXECUTE_STUB=1`, performs `git commit --allow-empty` (override exit via `FOUNDRY_EXECUTE_COMMIT_EXIT_CODE`).
- Writes `state.final_commit_sha` and links `execute.commit.final-commit` for Verify intake.
