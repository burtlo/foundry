# Intake checker — design history

Status: **reference** — documents the multi-mode `intake-checker` experiment and why v1 ships **shape-only** as `intake-checker.shape.md`.

**Current worker:** [`.cursor/agents/intake-checker.shape.md`](../../.cursor/agents/intake-checker.shape.md)  
**Contract:** [`.cursor/foundry/workers/intake-checker.shape/contract.yaml`](../../.cursor/foundry/workers/intake-checker.shape/contract.yaml)  
**Bound node:** `shape.intake` only in [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml)

---

## Feature overview

The intake checker is a **read-only assessment worker** launched during phase intake after lifecycle checks run. It helps the steward decide whether intake can proceed before publishing artifacts and sealing receipts.

| Phase | Intake node | Worker (v1) | Assessment focus |
|-------|-------------|-------------|------------------|
| Shape | `shape.intake` | **`intake-checker.shape`** | Work-request capture, ticket field draft, manifest readability |
| Execute | `execute.intake` | `intake-checker.execute` *(stub — prompt/contract not written yet)* | Plan vs approved AC alignment, external-plan sufficiency |
| Verify | `verify.intake` | `intake-checker.verify` *(stub — prompt/contract not written yet)* | Branch diff scope, AC review readiness |

`factory-flow.yaml` already binds `execute.intake` and `verify.intake` to `registry:agents/intake-checker.execute.md` and `registry:agents/intake-checker.verify.md` (plus matching contracts). Those registry files do not exist yet; steward step instructions and catalog checks gate those nodes until the prompts are written.

---

## Multi-mode design (archived)

Early v1 ports used **one prompt** (`intake-checker.md`) with a `mode` input (`shape` | `execute` | `verify`) and mode-specific task sections. The same contract YAML listed `valid_next_states` per mode.

### Why that was retired

1. **Different tasks, one file** — Shape captures tickets and reads manifests; execute compares plans to AC; verify assesses branch scope. A single `mode` switch produced a prompt written for authors, not for a subagent doing one job.
2. **Leaky orchestration** — Fields like `node_id`, `visit_id`, `run_id`, `intake_receipt_id`, and receipt schema jargon (`agent_assessment`, `checks[]`) belonged to the invoker, not the worker.
3. **Mode payload vs mode** — Listing `mode` in the inputs table and a separate "mode payload" section duplicated the same concept.
4. **Path B** — Catalog check results belong on the intake receipt (steward builds from ledger), not in worker I/O. Multi-mode prompts kept re-explaining what **not** to do.
5. **Per-node inputs differ** — `shape.intake` `reads` (`ticket`, `app_folder`, `workspace`) do not match execute (`approved_ac`, `plan_path`, …) or verify (`feature_branch`, …). One generic inputs table could not reflect the flow schema.

### Direction

- **One prompt per intake role** — `intake-checker.shape.md` now; execute/verify when those nodes need workers.
- **Shape prompt** — Minimal inputs the worker actually uses (`app_folder`, `work_prompt`, optional ticket hints). Output is assessment markdown + `blockers[]`; invoker stamps visit metadata when sealing.
- **Contracts** — `intake-checker.shape.yaml` with shape-only `valid_next_states`. Retire multi-mode `intake-checker.yaml` (archived below).

Related: [README.md](README.md) (POC import rules), [check-lookup-cli.md](check-lookup-cli.md) (Path A′ for future check introspection).

---

## Archived contract (`intake-checker.yaml`, multi-mode)

```yaml
capabilities:
  - intake
  - manifest_validation
required_output_fields:
  - outputs.summary_markdown
  - outputs.intake_receipt_id
modes:
  shape:
    valid_next_states:
      - shape.examine
  execute:
    valid_next_states:
      - execute.branch
  verify:
    valid_next_states:
      - verify.acceptance
```

---

## Archived prompt (`intake-checker.md`, multi-mode)

Full text as of 2026-09-24 before split to shape-only:

```markdown
---
name: intake-checker
description: >-
  Read-only intake assessment: work-request capture, manifest readability,
  and plan alignment for shape, execute, or verify intake steps.
model: fast
readonly: true
---

# Intake checker

## Purpose

Assess intake readiness from the invocation inputs. Return structured fields the invoker uses for `agent_assessment` on the intake receipt and for the agent receipt.

Read-only. Use only supplied inputs.

## Inputs

| Field | Required | Role |
|---|---|---|
| `mode` | yes | `shape`, `execute`, or `verify` |
| `node_id`, `visit_id`, `run_id` | yes | Active intake visit |
| `intake_receipt_id` | when known | Copy to `outputs.intake_receipt_id` |
| `app_folder` | yes | Resolved application repository root (`state.app_folder`) |
| Mode payload | yes | Below |

**`shape` payload:** user work prompt; optional draft ticket fields; optional `issue_key` or labels.

**`execute` payload:** `approved_ac`, `plan_path`, `intake_path`, `entry_reason`; plan content or `shape.record.plan` when shaped.

**`verify` payload:** `approved_ac`, `plan_path`, `feature_branch`, `default_branch`; plan and commit evidence; branch diff path when available.

If required inputs are missing, set `status: failed`, `blockers[]` to what is missing, and use **Verdict: BLOCKED** in `summary_markdown` with findings explaining the gap.

## Task

### `shape`

- Confirm a work request is present — any non-empty input is enough.
- Propose ticket fields for the steward:
  - `raw_input`, `normalized_translation`
  - `source_type`: `chat`, `paste`, `file`, `url`, or `repo_inference`
  - `source_ref`, `issue_key` when applicable
- Review `.foundry/app.yaml` under `app_folder` for readability: broken references, builder routes, verification commands that would block build later. Cite paths.

### `execute`

- Compare plan content to `approved_ac`. Note gaps, ambiguity, or scope drift.
- When `intake_path` is `non_shaped`, state whether the external plan is sufficient to build.
- When `entry_reason` is `verify_rework`, summarize rework context.

### `verify`

- Assess whether whole-branch review (`feature_branch` vs `default_branch`) and plan/AC alignment are ready for acceptance review.

## Output

Return these fields:

| Field | Type | Rule |
|---|---|---|
| `status` | string | `completed` when assessment is done; `failed` when required inputs were missing |
| `outputs.intake_receipt_id` | uuid | Copy from inputs when provided |
| `outputs.summary_markdown` | string | Full markdown document — **exact template below** |
| `blockers[]` | string[] | Human-readable reasons intake cannot proceed; `[]` when verdict is PROCEED |

**`blockers[]`:** one string per blocking issue (path + problem). The invoker may surface these on the intake receipt. When verdict is PROCEED, return an empty array.

### `outputs.summary_markdown` template

Use this structure every time. Replace `{placeholders}`. Keep headings exactly as shown.

# Intake assessment

**Verdict:** PROCEED | BLOCKED
**Mode:** {mode}
**Node:** {node_id} · **Visit:** {visit_id}

## Findings

- {bullet: finding with path when applicable}
- {bullet}

## Ticket draft

(shape mode only — omit for execute and verify)

| Field | Proposed value |
|-------|----------------|
| raw_input | {verbatim or faithful capture} |
| normalized_translation | {summary for downstream shape steps} |
| source_type | {chat \| paste \| file \| url \| repo_inference} |
| source_ref | {path, url, or null} |
| issue_key | {key or null} |

## Verdict summary

{One paragraph: what you assessed, why PROCEED or BLOCKED, and what the invoker should do next before sealing receipts.}

*(Example and JSON return bundle omitted here — see git history for full file.)*
```

---

## Deferred: execute and verify workers

When adding workers for `execute.intake` and `verify.intake`:

| Node | Likely inputs (from `reads`) | Likely assessment |
|------|------------------------------|-------------------|
| `execute.intake` | `app_folder`, `approved_ac`, `plan_path`, `intake_path`, `entry_reason`, plan artifact | Plan vs AC alignment; external plan sufficiency |
| `verify.intake` | `app_folder`, `approved_ac`, `plan_path`, `feature_branch`, `default_branch`, plan + commit artifacts, diff path | Acceptance review readiness |

Use separate prompt + contract files (`intake-checker.execute.md`, `intake-checker.verify.md`, …). Flow bindings for execute/verify are already in place as forward references.
