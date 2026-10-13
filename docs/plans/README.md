# Open plans and authoring aids

**Completed delivery** is captured in [docs/features/](../features/README.md) (feature records), [operator-runbook.md](../operator-runbook.md), and git (`git log --grep='REL-'`). This directory holds **incomplete** work and **how-to** guides—not shipped behavior. Delivered plans are removed after ship; use git history for prior plan text.

## Open work

| Plan | Status |
|------|--------|
| [operator-onboarding-ergonomics-retro.md](operator-onboarding-ergonomics-retro.md) | Open — porcelain first-run product experience and design investigation |
| [operator-onboarding-foundry-self-workspace-retro.md](operator-onboarding-foundry-self-workspace-retro.md) | Open — run `foundry-0001`; human handoff, questions, and answer workflow investigation |
| [foundry-0001-run-evaluation.md](foundry-0001-run-evaluation.md) | Artifacts-only evaluation of `foundry-0001` at the `user_input` wait |
| [expression-language-backlog.md](expression-language-backlog.md) | Open — narrow docs vs typed evaluator (track 2 shipped for implementation flow) |
| [deferred-contract-slices.md](deferred-contract-slices.md) | Open — optional shape.examine / present.gate slices |
| [cli-test-speed-plan.md](cli-test-speed-plan.md) | Proposed — pytest performance |

## Authoring (not feature records)

| Document | Use when |
|----------|----------|
| [workflow-node-revision-patterns.md](workflow-node-revision-patterns.md) | Changing a node contract (judgment vs engine vs steward) |
| [workflow-node-review-prompt.md](workflow-node-review-prompt.md) | Reviewing one workflow node in a dedicated chat |

### Operator onboarding retros

Each retro is a **standalone product experience investigation** in `docs/plans/operator-onboarding-<slug>-retro.md`. It preserves the operator's questions, expectations, commands tried, and friction, then traces each issue to current code/docs and explores improvement options with tradeoffs. The conversation is evidence of the operator's experience, not an audit of the helper's advice.

**To author or extend a retro:** run **`/operator-onboarding-retro`** and attach the run or existing evaluation when relevant. `/evaluate-run` owns run correctness, gates, judgment, and deliverables. The retro links that assessment and records the human experience that run artifacts alone cannot show.

- Skill: [.cursor/skills/operator-onboarding-retro/SKILL.md](../../.cursor/skills/operator-onboarding-retro/SKILL.md)
- Command: [.cursor/commands/operator-onboarding-retro.md](../../.cursor/commands/operator-onboarding-retro.md)
