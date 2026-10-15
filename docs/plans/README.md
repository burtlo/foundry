# Open plans and authoring aids

**Completed delivery** is captured in [docs/features/](../features/README.md) (feature records), [operator-runbook.md](../operator-runbook.md), and git (`git log --grep='REL-'`). This directory holds **incomplete** work and **how-to** guides—not shipped behavior. Delivered plans are removed after ship; use git history for prior plan text.

## Open work

| Plan | Status |
|------|--------|
| [foundry-up/](foundry-up/) | Open — [spec](foundry-up/spec.md) approved; [implementation map](foundry-up/implementation.md) merged (P1–P10 packages) — ready for orchestrated build |
| [cli-operator-ux/](cli-operator-ux/) | Open — [spec](cli-operator-ux/spec.md) approved; `up`/`down`, grouped help, `shape` intake handoff — ready for implementation map |
| [operator-onboarding-foundry-self-workspace-retro.md](operator-onboarding-foundry-self-workspace-retro.md) | Open — legacy path; run `foundry-0001` handoff investigation |
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

Operator work is grouped in **plan bundles**: `docs/plans/<bundle>/` with `retro.md` (experience investigation), optional `spec.md` (feature specification after interview), and `README.md` (index). Legacy flat files `operator-onboarding-<slug>-retro.md` may still exist; `/retro-feature-interview` can move them into a named bundle.

**To author or extend a retro:** run **`/operator-onboarding-retro`** (optional `bundle` name) and attach the run or existing evaluation when relevant. `/evaluate-run` owns run correctness, gates, judgment, and deliverables. The retro links that assessment and records the human experience that run artifacts alone cannot show.

- Skill: [.cursor/skills/operator-onboarding-retro/SKILL.md](../../.cursor/skills/operator-onboarding-retro/SKILL.md)
- Command: [.cursor/commands/operator-onboarding-retro.md](../../.cursor/commands/operator-onboarding-retro.md)

### Retro → feature specification

After investigations are captured, run **`/retro-feature-interview @docs/plans/<bundle>/retro.md`** (or a legacy retro file) to decide scope through clarifying questions and publish **`docs/plans/<bundle>/spec.md`** beside the retro. The command creates or names the bundle when needed. The interview mirrors `shape.examine` grilling: few questions per turn, explicit rationale, decisions and acceptance criteria in the bundle.

- Skill: [.cursor/skills/retro-feature-interview/SKILL.md](../../.cursor/skills/retro-feature-interview/SKILL.md)
- Command: [.cursor/commands/retro-feature-interview.md](../../.cursor/commands/retro-feature-interview.md)

### Spec → implementation map

After **`spec.md`** is approved (or stable enough to build against), run **`/spec-implementation-map @docs/plans/<bundle>/spec.md`** to explore the codebase, record present vs required behavior, and publish **`implementation.md`** in the same bundle. The map packages work for an orchestrator agent (implementer and verifier assignments, dependencies, test hooks) without starting implementation in the mapping session.

- Skill: [.cursor/skills/spec-implementation-map/SKILL.md](../../.cursor/skills/spec-implementation-map/SKILL.md)
- Command: [.cursor/commands/spec-implementation-map.md](../../.cursor/commands/spec-implementation-map.md)
- Example: [foundry-up/implementation.md](foundry-up/implementation.md)
