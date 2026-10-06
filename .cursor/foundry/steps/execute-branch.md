# execute.branch

Create and validate the feature branch deterministically. **No model may create a branch.**

## Naming

- Default pattern: `foundry/{run_slug}` where `run_slug` is run state or `run_id`.
- Optional: `foundry/{developer_first_name}/{run_slug}` when `developer_first_name` is set in state.
- Names must match `foundry/…` kebab-safe rules enforced by the host.

## Host behavior

1. Resolve `default_branch` from the git workspace.
2. Compute expected `feature_branch` name; reject invalid names.
3. If the branch exists, check it out; otherwise create from default with `git checkout -b`.
4. Record `default_branch`, `feature_branch`, `feature_branch_head`, and placeholder `execution_graph_id` for `execute.plan` admission checks.
5. Seal visit and route to `execute.plan`.

## Steward / operator

Do not run `git checkout` or branch creation manually unless recovering from a host error. Use `run advance` after `execute.intake.gate` passes.
