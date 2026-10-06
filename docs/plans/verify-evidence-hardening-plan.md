# Verify evidence hardening plan

Status: implemented 2026-10-06. Closes P1/P2 gaps from post–2C–2F review: verify receipts and gates must fail closed until evidence supports the decision.

## Goals

1. **Verify intake** — Do not seal `passed` or transition when branch/diff/context is unusable; mirror `execute.intake` blocked semantics.
2. **Verify acceptance** — Derive `gate_decision` and per-criterion status from sealed context + branch diff (not env default). Env override only under explicit test stub (`FOUNDRY_EXECUTE_STUB=1`).
3. **Code quality** — Off stub path, run manifest `code_quality` / `lint` or fail closed (no fake exit 0).
4. **Gates** — Intake gate must not pass on failed/blocked receipts; acceptance gate must reject findings without `evidence_ok` / valid assessment.
5. **Tests** — Unit tests for failure modes; keep forward E2E under stub; add non-stub acceptance assessment test where feasible; review-disabled skip; quality repair route.
6. **Docs** — Update step markdown, refresh `node-inventory.md` boundary snapshot, note behavior in this plan.

## Phases (implement → verify → commit)

| Phase | Scope | Acceptance |
| --- | --- | --- |
| **A** | `verify_step_executor.py` intake + acceptance + code quality | Intake blocked without SHA/branch/diff; acceptance pass only with assessable diff; quality fails without manifest command when stub off |
| **B** | `gates.py` tighten intake/acceptance resolvers | Gate cannot pass on blocked intake or `evidence_ok: false` findings |
| **C** | `test_verify_evidence.py` + extend `test_workflow_slices_2c_2f.py` | New failures green; stub forward path still reaches `deliver.stub` |
| **D** | Steps + `node-inventory.md` header | Docs match shipped behavior |

## Acceptance assessment rules (deterministic)

Priority when not in stub override:

| Condition | `gate_decision` | `evidence_ok` |
| --- | --- | --- |
| Missing `approved_ac` | `reshape` | false |
| Missing `final_commit_sha` or tests not passed | `rework_execute` | false |
| Diff unavailable / git error / empty diff | `rework_execute` | false |
| Tests passed, context OK | `replan` (AC listed as `not_verified`) | false |

Host **never** marks AC `met` from diff substring match. Gate `pass` requires `evidence_ok: true` explicitly (stub integration only until validator step exists).

Stub override: `FOUNDRY_VERIFY_ACCEPTANCE_DECISION` honored only when `FOUNDRY_EXECUTE_STUB=1`; `evidence_ok` true only for stub `pass`.

## Verify intake git linkage

`final_commit_sha` must resolve to a commit, be reachable on `feature_branch`, and equal `git rev-parse feature_branch` tip. Diff scope remains `default...feature`.

## Out of scope

- Real LLM acceptance review (future model-bound step).
- Full fresh-workspace Shape→Deliver feature (workflow-02 final acceptance).
- `foundry dev docs` run (recommended follow-up after merge).
