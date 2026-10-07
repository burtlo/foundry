# Agent adapter integration plan

Status: **active** — enables Cursor/cloud agents and real judgment tasks (starting with **G1**).  
**Parent:** [release-charter.md](release-charter.md) waves **R-2**, **R-3**.  
**Gap:** [shape-execute-verify-gap-closure-plan.md](shape-execute-verify-gap-closure-plan.md) **G1**, tests **T1**, **T5**.  
**Architecture:** [job-host-architecture.md](../concepts/job-host-architecture.md) Agent connection contract; [engine-kernel-unify-plan.md](engine-kernel-unify-plan.md) Phase 3.

## Scope

| Item | Notes |
| --- | --- |
| Bind `implementation-validator` (or equivalent) to `verify.acceptance` | Task YAML, output schema, applicator → `verify_findings` + gate resolver |
| Registry-driven task input builders | Replace open-ended `tasks.py` `if task_id` growth; register per task id |
| `FOUNDRY_AGENT_ADAPTER=stub\|http` | Document HTTP contract matching `build_agent_request` / submit validation |
| Cursor SDK / cloud adapter | Implements `AgentAdapter.invoke`; no steward receipt forgery |

## Non-goals (this release)

- Unrestricted tool use from workflow YAML without host policy
- Replacing stub adapter in pytest (keep explicit `FOUNDRY_ALLOW_STUB_ADAPTER`)

## Exit

- Verify acceptance `pass` with sealed findings and `evidence_ok: true` under Step 0 policy — no `FOUNDRY_VERIFY_ACCEPTANCE_DECISION` in production path
- Documented adapter setup for invoking agents against app workspaces

## Related node contracts (authoring only — behavior delivered here)

- [verify.acceptance-contract-cleanup-plan.md](verify.acceptance-contract-cleanup-plan.md)
- [verify.acceptance.gate-contract-cleanup-plan.md](verify.acceptance.gate-contract-cleanup-plan.md)
