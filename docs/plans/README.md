# Open plans and authoring aids

**Completed delivery** is captured in [docs/features/](../features/README.md) (feature records), [operator-runbook.md](../operator-runbook.md), and git (`git log --grep='REL-'`). This directory holds **incomplete** work and **how-to** guides—not shipped behavior. Delivered plans are removed after ship; use git history for prior plan text.

## Open work

| Plan | Status |
|------|--------|
| [foundry-up/](foundry-up/) | Open — [spec](foundry-up/spec.md) approved; [implementation map](foundry-up/implementation.md) merged (P1–P10 packages) — ready for orchestrated build |
| [cli-operator-ux/](cli-operator-ux/) | Open — [spec](cli-operator-ux/spec.md) approved; [implementation map](cli-operator-ux/implementation.md) (P1–P9) — ready for orchestrated build |
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

**To author or extend a retro:** run **`/capture-product-feedback`** (optional `bundle` name) and attach the run or existing evaluation when relevant. `/evaluate-run` owns run correctness, gates, judgment, and deliverables. The retro links that assessment and records the human experience that run artifacts alone cannot show.

- Skill: [.cursor/skills/capture-product-feedback/SKILL.md](../../.cursor/skills/capture-product-feedback/SKILL.md)

### Retro → feature specification

After investigations are captured, run **`/retro-feature-interview @docs/plans/<bundle>/retro.md`** (or a legacy retro file) to decide scope through clarifying questions and publish **`docs/plans/<bundle>/spec.md`** beside the retro. The skill creates or names the bundle when needed. The interview mirrors `shape.examine` grilling: few questions per turn, explicit rationale, decisions and acceptance criteria in the bundle.

- Skill: [.cursor/skills/retro-feature-interview/SKILL.md](../../.cursor/skills/retro-feature-interview/SKILL.md)

### Spec → implementation map

After **`spec.md`** is approved (or stable enough to build against), run **`/spec-implementation-map @docs/plans/<bundle>/spec.md`** to explore the codebase, record present vs required behavior, and publish **`implementation.md`** in the same bundle. The map packages work for an orchestrator agent (implementer and verifier assignments, dependencies, test hooks) without starting implementation in the mapping session.

- Skill: [.cursor/skills/spec-implementation-map/SKILL.md](../../.cursor/skills/spec-implementation-map/SKILL.md)
- Example: [foundry-up/implementation.md](foundry-up/implementation.md)

### Map → orchestrated build

After **`implementation.md`** is **ready for orchestration**, run **`/orchestrate-build @docs/plans/<bundle>/`** or **`/orchestrate-build @docs/plans/<bundle>/implementation.md`**. The orchestrator delegates each package **P1…Pn** to **plan-implementer**, then an independent **plan-verifier** subagent; it does not implement product code itself. Progress is recorded in **`orchestration-progress.md`** in the bundle.

- Skill: [.cursor/skills/orchestrate-build/SKILL.md](../../.cursor/skills/orchestrate-build/SKILL.md)
- Agents: [plan-implementer](../../.cursor/agents/plan-implementer.md), [plan-verifier](../../.cursor/agents/plan-verifier.md)
