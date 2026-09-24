---
step_id: implement.branch
title: Create the feature branch
subagent: null
run_modes: [implementation]
delivery_gate: false
state_keys:
  - steps.implement.branch.status
  - default_branch
  - feature_branch
  - feature_branch_head
---

## Purpose

Get off the recorded start point (or detected default branch) before any file changes. `delivery-check` fails when `feature_branch` is unset or equal to `default_branch`, so this step is what makes shipping possible later.

When `state.start_point` is set (from `run init --start-point`), `branch create` bases the feature branch on that ref, records it as `default_branch` (PR `--base`), and does **not** check out or pull `main`/`master`.

## Inputs (from parent)

- FactoryConfig slice: `git.feature_branch_pattern`, `git.default_branch`
- `issue_key`, `developer_first_name`

## Parent actions

1. If `state.start_point` is unset, resolve the default branch:

```foundry-invoke
git default-branch --repo "{app_folder}"
```

Skip this lookup when `start_point` is already recorded — do not check out `main`.
2. Expand the branch name from `git.feature_branch_pattern` (or `branch-name`).
3. Create and record it. Without `start_point` this checks out the detected default, pulls, and branches. With `state.start_point` it branches from that ref and skips pull:

```foundry-invoke
branch create --state "{state_path}" --repo "{app_folder}" --name {feature_branch}
```

The command records `default_branch`, `feature_branch`, and `feature_branch_head`; do not duplicate those writes with `transition --set`. If `state.start_point` is set, it is used automatically — do not pass a different `--start-point`.

## Launch packet (pass to Task; not parent work)

None.

## State keys this step owns

- `steps.implement.branch.status`
- `default_branch`
- `feature_branch`
- `feature_branch_head`

## Gate

None. Requires `steps.plan.brief.human_approved` and `steps.plan.graph.human_approved`.

## Invalid transitions

- `implement.build` requires `state.feature_branch`, so the engine rejects building on the default branch.
- Do not commit here. The first commit happens at `deliver.ship`, after `delivery-check` passes.
