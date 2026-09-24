---
step_id: implement.code_review
title: Human code review
subagent: null
run_modes: [implementation]
delivery_gate: false
state_keys:
  - steps.implement.code_review.status
  - steps.implement.code_review.approved
  - steps.implement.code_review.human_approved
  - steps.implement.code_review.gate_decision
---

## Purpose

The human reads the actual diff and approves the implementation. This is the gate everything after it hangs off: devops review, pre-PR review, documentation, and every `deliver.*` step declare it as a requirement.

## Inputs (from parent)

- Working-tree diff for the feature branch
- `approved_ac` and the approved brief
- Validator receipt from `implement.validate`
- FactoryConfig slice: `templates.code_review`

## Parent actions

1. Show a change summary (files, why) and a **diff command pointer** (do not paste megabyte diffs). Map each AC to where it is satisfied — prefer AskQuestion / handoff file over dumping the full diff in chat.
2. Collect `approve` or `code_changes`. Do **not** edit app source to “help”; route `code_changes` back to `implement.build`.
3. On approve, run `gate resolve --state "{state_path}" --config "{config_path}" --source human --decision approve`.
4. This is a **ready-for-PR** hard stop in all interaction modes. Write `run handoff` and stop unless the user said keep going.

Nothing is committed at this step.

## Launch packet (pass to Task; not parent work)

None. This is a human gate.

## State keys this step owns

- `steps.implement.code_review.status`
- `steps.implement.code_review.approved`
- `steps.implement.code_review.human_approved`
- `steps.implement.code_review.gate_decision`

## Gate

`human_approval` (`approve_implementation`). Blocks `implement.devops_review`, `implement.pre_pr_review`, `implement.documentation`, and all `deliver.*` steps.

## Invalid transitions

- `implement.documentation` declares `requires: state.steps.implement.code_review.human_approved`. Documentation before an approved code review is rejected by `transition`, not just discouraged.
- `delivery-check` re-asserts the same condition as `CODE_REVIEW`, so skipping the gate cannot be laundered through a later step.
- `delivery_gate: false` here is deliberate: this step is the *precondition*, and the gated evidence lives on the review steps that follow.
