---
step_id: deliver.gate
title: Pre-delivery evidence gate
subagent: null
run_modes: [implementation]
delivery_gate: true
state_keys:
  - steps.deliver.gate.status
  - steps.deliver.gate.notes
---

## Purpose

One machine check that every piece of delivery evidence exists before anything leaves the machine.

## Inputs (from parent)

- Full `steps` evidence map
- FactoryConfig slice: `devops`, `review`

## Parent actions

1. Run:

```foundry-invoke
delivery-check --state "{state_path}" --config "{config_path}"
```
2. Exit 0: mark the step complete and move on.
3. Non-zero: read `failures`, transition back to the step that owns the missing evidence, and re-run. Do not narrate the gate as passed.

## Delivery-check matrix

| Code | Condition | Applies when |
|------|-----------|--------------|
| `CODE_REVIEW` | `steps.implement.code_review.human_approved` is true | always |
| `DOCUMENTATION` | `steps.implement.documentation.report == 'received'` and `human_approved` is true | always |
| `DOCUMENTATION_PUBLICATION` | pipeline/result `publication.passed` is true | `publication.required` is true |
| `SYNC_PRD` | `steps.implement.documentation.sync_prd_ok` is true | IoT alias of `DOCUMENTATION_PUBLICATION` when a PRD was created or updated |
| `DEVOPS_REVIEW` | `steps.implement.devops_review.report == 'received'` and `human_approved` is true | `config.devops.enabled` and `config.devops.run_before_pr` |
| `PRE_PR_REVIEW` | `steps.implement.pre_pr_review.report == 'received'` and `human_approved` is true | `config.review.enabled` and `config.review.run_before_pr` |
| `PRE_PR_CRITICS` | Bound critic receipts are valid for `config.review.mode` (run ID, launch ID, step, HEAD) | `config.review.enabled` and `config.review.run_before_pr` |
| `POST_REPAIR` | `rework.post_repair_ok` is true and `post_repair_head` matches current HEAD | mutating repair ran (`rework.post_repair_required`, failed post-repair, or a completed repair item) |
| `FEATURE_BRANCH` | `feature_branch` is set and differs from `default_branch` | always |
| `PR_EXTRAS` | `pr_extras_register` is an array (empty allowed) | always |

## Launch packet (pass to Task; not parent work)

None.

## State keys this step owns

- `steps.deliver.gate.status`
- `steps.deliver.gate.notes`

## Gate

`evidence_only` (`delivery_check`). There is no human prompt and nothing for the engine to wait on here — the enforcement is `require_delivery_check` on `deliver.scope_comment` and `deliver.ship`, which re-runs the check on entry.

## Invalid transitions

- `deliver.scope_comment` and `deliver.ship` both carry `require_delivery_check: true`, so `transition` re-runs `delivery-check` and refuses to move when it fails. Story approval alone is never sufficient.
- No `git commit`, no `git push`, no `gh pr create` before this step completes.
- When `publication.required` is true, `publication.passed` must be true (`DOCUMENTATION_PUBLICATION`; IoT alias `SYNC_PRD`). `feature-records` does not require sync-prd.
