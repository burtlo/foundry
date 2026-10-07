# Open plans and authoring aids

**Completed delivery** is captured in [docs/features/](../features/README.md) (feature records), [operator-runbook.md](../operator-runbook.md), and git (`git log --grep='REL-'`). This directory holds **incomplete** work and **how-to** guides—not shipped behavior. Delivered plans are removed from this tree or moved to [archive/](archive/README.md) after ship.

## Operator integration

| Document | Status |
|----------|--------|
| [operator-integration-program.md](operator-integration-program.md) | **Complete** (phases 0–6) |
| [archive/](archive/README.md) | Archived phase plans (auto-advance, TUI protocol, Textual TUI, integration smoke) |

## Other open work

| Plan | Status |
|------|--------|
| [expression-language-backlog.md](expression-language-backlog.md) | Open — narrow docs vs typed evaluator (track 2 shipped for implementation flow) |
| [deferred-contract-slices.md](deferred-contract-slices.md) | Open — optional shape.examine / present.gate slices |
| [cli-test-speed-plan.md](cli-test-speed-plan.md) | Proposed — pytest performance |

## Authoring (not feature records)

| Document | Use when |
|----------|----------|
| [workflow-node-revision-patterns.md](workflow-node-revision-patterns.md) | Changing a node contract (judgment vs engine vs steward) |
| [workflow-node-review-prompt.md](workflow-node-review-prompt.md) | Reviewing one workflow node in a dedicated chat |
