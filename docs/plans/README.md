# Implementation plans

Active workflow implementation lives here. Registry and generated references: [docs/index.md](../index.md), [node-inventory.md](node-inventory.md).

| Document | Use when |
| --- | --- |
| [orchestrator-brief.md](orchestrator-brief.md) | Sequencing work with implement/verify subagents |
| [workflow-node-review-prompt.md](workflow-node-review-prompt.md) | Review one workflow node at a time |
| [shape-examine-contract-cleanup-plan.md](shape-examine-contract-cleanup-plan.md) | **Proposed** — `shape.examine` contract cleanup |
| [shape-execute-verify-gap-closure-plan.md](shape-execute-verify-gap-closure-plan.md) | **Current** gaps G1–G10, tests, slice order |
| [remaining-nodes-orchestrator-runbook.md](remaining-nodes-orchestrator-runbook.md) | Step 0–2 procedure, evidence gates |
| [workflow-02-step0-decisions.md](workflow-02-step0-decisions.md) | Policy decisions (F1–F9) |
| [execute-verify-boundary-audit.md](execute-verify-boundary-audit.md) | Regenerate from `node_capability.audit_rows` |

**Delivered (no separate plan file):** `shape.intake` contract cleanup — see [shape-deterministic-extraction.md](../shape-deterministic-extraction.md). Job host Phases 0–7 — see [concepts/job-host-architecture.md](../concepts/job-host-architecture.md).
