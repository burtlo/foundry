# Open plans and authoring aids

**Completed delivery** is captured in [docs/features/](../features/README.md) (feature records), [operator-runbook.md](../operator-runbook.md), and git (`git log --grep='REL-'`). This directory holds **incomplete** work and **how-to** guides—not shipped behavior. Delivered plans are removed after ship; use git history for prior plan text.

## Open work

| Plan | Status |
|------|--------|
| [operator-onboarding-ergonomics-retro.md](operator-onboarding-ergonomics-retro.md) | Open — porcelain first-run retro; host/bridge/CLI UX backlog for agent review |
| [expression-language-backlog.md](expression-language-backlog.md) | Open — narrow docs vs typed evaluator (track 2 shipped for implementation flow) |
| [deferred-contract-slices.md](deferred-contract-slices.md) | Open — optional shape.examine / present.gate slices |
| [cli-test-speed-plan.md](cli-test-speed-plan.md) | Proposed — pytest performance |

## Authoring (not feature records)

| Document | Use when |
|----------|----------|
| [workflow-node-revision-patterns.md](workflow-node-revision-patterns.md) | Changing a node contract (judgment vs engine vs steward) |
| [workflow-node-review-prompt.md](workflow-node-review-prompt.md) | Reviewing one workflow node in a dedicated chat |
