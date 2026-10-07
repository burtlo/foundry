# Implementation plans

Active workflow implementation lives here. **Release sequencing:** [release-charter.md](release-charter.md). Registry and generated references: [docs/index.md](../index.md), [node-inventory.md](node-inventory.md).

## Release and runtime

| Document | Use when |
| --- | --- |
| [release-charter.md](release-charter.md) | **Start here** — delivery waves R-0–R-7, links to all plans in order |
| [engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) | Untangle `advance` / executors / tasks vs registry |
| [agent-adapter-integration-plan.md](agent-adapter-integration-plan.md) | Real judgment tasks + Cursor/HTTP adapter (**G1**) |
| [step1-runtime-prerequisites-plan.md](step1-runtime-prerequisites-plan.md) | Runbook Step 1 checklist (partial) |
| [release-integration-plan.md](release-integration-plan.md) | Final E2E and **T1–T10** before COMPLETE |
| [shape-execute-verify-gap-closure-plan.md](shape-execute-verify-gap-closure-plan.md) | Findings **G1–G10**, scenarios, definition of COMPLETE |
| [orchestrator-brief.md](orchestrator-brief.md) | Sequencing work with implement/verify subagents |
| [remaining-nodes-orchestrator-runbook.md](remaining-nodes-orchestrator-runbook.md) | Step 0–2 procedure, evidence gates |
| [workflow-02-step0-decisions.md](workflow-02-step0-decisions.md) | Policy decisions (F1–F9) |
| [execute-verify-boundary-audit.md](execute-verify-boundary-audit.md) | Regenerate from `node_capability.audit_rows` |

## Contract revision (per node)

| Document | Use when |
| --- | --- |
| [workflow-node-revision-orchestration.md](workflow-node-revision-orchestration.md) | All 29 nodes — revision program **COMPLETE** |
| [workflow-node-revision-patterns.md](workflow-node-revision-patterns.md) | Judgment vs engine vs steward patterns |
| [workflow-node-review-prompt.md](workflow-node-review-prompt.md) | Review one workflow node at a time |
| [shape-examine-contract-cleanup-plan.md](shape-examine-contract-cleanup-plan.md) | `shape.examine` — **done** (slice 7 deferred) |
| Per-node `*-contract-cleanup-plan.md` | Full table in [release-charter.md](release-charter.md) §3 |

**Delivered (no separate plan file):** `shape.intake` — [shape-deterministic-extraction.md](../shape-deterministic-extraction.md). Job host Phases 0–7 — [concepts/job-host-architecture.md](../concepts/job-host-architecture.md).
