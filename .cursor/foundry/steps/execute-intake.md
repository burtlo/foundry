# execute.intake

Host-owned deterministic intake at Execute entry. No model on the happy path.

## Preconditions

- Sealed `shape.record` with `approved_ac`, `plan_path`, and linked `shape.record.plan` artifact.
- User authorized Execute via `foundry start` at `execute.start`.
- Git worktree clean (`validate-git-clean-execute` on admit).

## Steward / operator actions

The Foundry host advances this step automatically when the active visit is `execute.intake` and lifecycle is `opened`. Do not invoke the intake-checker worker for receipt mechanics on the default path.

## Evidence recorded

1. Validate frozen shape state and on-disk plan markdown.
2. Write `run:receipts/assessment.md` with PROCEED or BLOCKED findings.
3. Seal `registry:schemas/intake-receipt.schema.json` and `registry:schemas/agent-receipt.schema.json` for this visit.
4. Patch `intake_path` / `entry_reason` when intake passes.
5. `transition` to `execute.intake.gate` on pass.

## Failure

- Missing shape artifacts: intake receipt `status: blocked`; visit stays opened (no route).
- Git not clean: halted on admit before host intake runs.
