# Workflow node revision orchestration

**Status:** in progress  
**Scope:** Remaining `factory-flow.yaml` step/gate nodes after shape.present.gate cleanup.

## Already revised (do not re-scope)

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

## Remaining nodes (workflow order)

5. `execute.branch`
6. `execute.plan`
7. `execute.build`
8. `execute.test`
9. `execute.test.gate`
10. `execute.repair.limit.gate`
11. `execute.commit`
12. `execute.commit.gate`
13. `verify.intake`
14. `verify.intake.gate`
15. `verify.acceptance`
16. `verify.acceptance.gate`
17. `verify.code_quality`
18. `verify.code_quality.gate`
19. `verify.code_review`
20. `verify.code_review.gate`
21. `verify.complete`
22. `verify.complete.gate`
23. `deliver.stub`

## Per-node cycle (orchestrator)

For each `NODE_ID`:

1. **Implementer subagent** — Follow [workflow-node-review-prompt.md](workflow-node-review-prompt.md) with `{NODE_ID}` replaced. Trace implementation, classify responsibilities, propose minimal schema. Write an actionable plan at `docs/plans/{NODE_ID}-contract-cleanup-plan.md` (mirror [shape-present-gate-contract-cleanup-plan.md](shape-present-gate-contract-cleanup-plan.md)). **Implement** the smallest concrete changes: `factory-flow.yaml` node block, `registry:nodes/{NODE_ID}/`, catalog index, generated docs (`doc build` if applicable), tests, engine/CLI only where required. Run targeted tests; **do not commit**.
2. **Verifier subagent** — Re-run review checklist against the plan, confirm tests and docs, fix gaps, draft commit message, **create one git commit** for that node’s changes only.

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
