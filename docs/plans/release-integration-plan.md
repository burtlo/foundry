# Release integration plan

Status: **pending** — final gate before implementation-flow release is **COMPLETE**.  
**Parent:** [release-charter.md](release-charter.md) wave **R-7**.  
**Definition of COMPLETE:** [shape-execute-verify-gap-closure-plan.md](shape-execute-verify-gap-closure-plan.md) §F.  
**Scenarios:** same doc §D (**T1**–**T10**).

## Scope

| ID | Scenario | Depends on |
| --- | --- | --- |
| T1 | E2E Shape → Execute (manifest) → Verify → `deliver.stub` without verify env override | **G1**, **G3**, [agent-adapter-integration-plan.md](agent-adapter-integration-plan.md) |
| T2 | `shape.record.gate` hold → advance → status not erroneous `completed` | **G2** |
| T3–T4 | Blocked execute/verify intake → recovery | **G5** |
| T5 | Acceptance findings `pass` + `evidence_ok: true` from validator artifact | **G1** |
| T6 | Each feedback route once (repair, replan, reshape, rework_execute) | Graph + gates |
| T7 | Repair limit → halt → `retry` | **G8** |
| T8 | Reverify limit on second verify entry | **G9** |
| T9 | Build boundary per G3 policy | **G3** |
| T10 | Resume after host restart at execute.start, verify gates | Host durability |

## Deliverables

- [acceptance README](../../.cursor/foundry/cli/tests/acceptance/README.md) updated for canonical (non-stub-default) path
- [node-inventory.md](node-inventory.md) + [execute-verify-boundary-audit.md](execute-verify-boundary-audit.md) regenerated
- [README.md](README.md) release charter status row set to **COMPLETE**

## Evidence gates

[orchestrator-brief.md](orchestrator-brief.md) — full `dev unit`, `dev acceptance`, `dev docs`, clean git diff on `docs` and `.cursor/foundry`.
