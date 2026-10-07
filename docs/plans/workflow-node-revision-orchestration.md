# Workflow node revision orchestration

**Status:** COMPLETE — all implementation-flow nodes revised.  
**Scope:** `flows/implementation/registry.yaml` step/gate nodes (shape through `deliver.stub`).

## Revised nodes (full set)

- `shape.intake`
- `shape.examine`
- `shape.examine.gate`
- `shape.present`
- `shape.present.gate`
- `shape.record`
- `shape.record.gate`
- `execute.start`
- `execute.intake`
- `execute.intake.gate`
- `execute.branch`
- `execute.plan`
- `execute.build`
- `execute.test`
- `execute.test.gate`
- `execute.repair.limit.gate`
- `execute.commit`
- `execute.commit.gate`
- `verify.intake`
- `verify.intake.gate`
- `verify.acceptance`
- `verify.acceptance.gate`
- `verify.code_quality`
- `verify.code_quality.gate`
- `verify.code_review`
- `verify.code_review.gate`
- `verify.complete`
- `verify.complete.gate`
- `deliver.stub`

## Per-node cycle (orchestrator-owned)

**Patterns for implementers:** [workflow-node-revision-patterns.md](workflow-node-revision-patterns.md) (read first every slice).

For each `NODE_ID`, the **orchestrator** runs two **sibling** sub-chats (implementer first, then verifier). The verifier is **not** spawned by the implementer — only the orchestrator launches it so verification stays visible in its own transcript.

1. **Implementer subagent** (`generalPurpose`) — Follow [workflow-node-review-prompt.md](workflow-node-review-prompt.md) and **patterns** doc. Plan at `docs/plans/{NODE_ID}-contract-cleanup-plan.md`. Implement + targeted tests. **Do not commit**; return summary, test commands, and deferred items.
2. **Verifier subagent** (`commit-agent`) — Launched by **orchestrator** after implementer returns. Re-check plan, run tests, fix small gaps, **one scoped commit**, no push.

## Architectural targets (all nodes)

- **Judgment → model** only where semantic reasoning is required.
- **Mechanism / policy → engine** (checks, lifecycle, operations, CLI).
- **Presentation → steward/renderer** (gate two-turn UX; no inflated worker prompts).
- Prefer one semantic complete operation over multi-step CLI orchestration in prose.
- Smallest correct schema: drop redundant `allow.*`, align `reads` with `run context`, bind workers only on happy path.

## Reference patterns

- Gate cleanup: [shape-present-gate-contract-cleanup-plan.md](shape-present-gate-contract-cleanup-plan.md)
- Upstream shape step pattern: sibling nodes under `.cursor/foundry/nodes/shape.*`

## Workspace

Repo: `/Users/lynnfrank/src/foundry` (Foundry registry bundle at `.cursor/foundry/`).
