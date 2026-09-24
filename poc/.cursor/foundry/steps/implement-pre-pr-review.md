---
step_id: implement.pre_pr_review
title: Pre-PR Bugbot and Security review
subagent: null
run_modes: [implementation]
delivery_gate: true
state_keys:
  - steps.implement.pre_pr_review.status
  - steps.implement.pre_pr_review.report
  - steps.implement.pre_pr_review.approved
  - steps.implement.pre_pr_review.human_approved
---

## Purpose

Run the automated critics on the branch diff before the PR is opened, so findings are fixed in the same review cycle rather than as PR comments. Runs when `config.review.enabled` and `config.review.run_before_pr` are both true.

## Inputs (from parent)

- FactoryConfig slice: `review.mode` (`both` | `bugbot` | `security` | `ask`), `review.diff`
- `feature_branch`

## Parent actions

1. `review.mode: ask` — ask the human which critics to run before launching anything.
2. Resolve the critic list:

```foundry-invoke
review critics --mode {mode}
```

3. For each critic, launch through Foundry (not a raw Task-only launch). `subagent` is null because there are two critics; pass `--agent` explicitly:

```foundry-invoke
worker launch-packet --state "{state_path}" --agent {critic} --mode review
```

Then Task with the packet prompt, then complete from `craft_staging_path` / `launch_id`. When mode is `both`, run `bugbot` then `security-review` sequentially.

4. After both critics complete:

```foundry-invoke
review validate-receipts --state "{state_path}"
```

5. Present the merged findings and collect `approve`, `fix_findings`, or `accept_risk`.
6. Record `steps.implement.pre_pr_review.report=received`, then resolve the gate with the human decision (`approve` or `accept_risk`).

The parent launches these through Foundry so receipts carry `launch_id`. `subagent` stays null in the registry because there is no single Foundry agent for this step.

## Launch packet (pass to Task; not parent work)

Use the prompt and bounded inputs from `worker launch-packet`. Default diff scope remains `branch changes` unless `review.diff` overrides it.

```text
Full Repository Path: {app_folder}
Diff: branch changes
```

## State keys this step owns

- `steps.implement.pre_pr_review.status`
- `steps.implement.pre_pr_review.report`
- `steps.implement.pre_pr_review.approved`

## Gate

`human_approval` (`approve_pre_pr_review`). Blocks `implement.documentation`, `deliver.gate`, and `deliver.ship`.

## Invalid transitions

- Fixing findings means going back to `implement.build` (`--decision fix_findings`), which re-runs `implement.validate` and `implement.code_review`.
- Workflow changes discovered here go back to `implement.devops_review` (`--decision workflows_changed`).
- Do not open the PR to get review coverage. This step exists precisely so the PR is not the review venue.
