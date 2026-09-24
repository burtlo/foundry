---
step_id: implement.documentation
title: Documentation workflow and PRD
subagent: documentation-writer
run_modes: [implementation]
delivery_gate: true
state_keys:
  - steps.implement.documentation.status
  - steps.implement.documentation.report
  - steps.implement.documentation.human_approved
  - steps.implement.documentation.prd_created_or_updated
  - steps.implement.documentation.sync_prd_ok
  - pr_extras_register
---

## Purpose

Mandatory documentation pass after code review and pre-PR review. Mechanical work is backend-resolved by `docs pipeline` from the snapshot `documentation.model`. Judgment (what changed, metadata interview when the model requires it, DocChangeReport) stays with documentation-writer.

Registered factory-shipped models: `iot-agents-prd`, `feature-records`. Do not invent a plugin loader. Unknown models fail before run creation.

## Inputs (from parent)

- Snapshot `documentation.model` and pipeline `workflow` (launch packet / project context)
- FactoryConfig slice: `templates.documentation_workflow`, `templates.sync_prd_caller`, `templates.sync_prd_validate_script`, `analysis` (IoT backend)
- Approved diff, `approved_ac`, `app_folder`, branch-point commit for `--since`

## Parent actions

1. Run the backend-resolved pipeline before launching the writer. Do **not** run `docs discover`, `docs audit`, `prd generate`, or `prd validate` in this step; those remain CLI helpers inside the `iot-agents-prd` backend.

```foundry-invoke
docs pipeline --state "{state_path}" --since {branch_point_commit}
```

2. Run:

```foundry-invoke
worker launch-packet --state "{state_path}"
```

Then launch `documentation-writer` with its exact prompt. Complete from `craft_staging_path`; the engine records the required durable receipt and report evidence. The writer follows snapshot `documentation.model` and the pipeline `workflow` field — not a hardcoded IoT workflow. For `iot-agents-prd`, the writer does **not** mechanically regenerate or re-read-validate the PRD when the pipeline already passed.

3. For exploration receipts from the run, propose knowledge (human approves promotion in this gate; nothing is auto-committed under `.cursor/foundry/knowledge/`):

```foundry-invoke
knowledge suggest --receipt {receipt_path} --factory-root "{factory_root}"
```

4. Publication runs **only if** pipeline/result `publication.required` is true (IoT when a PRD changed). `feature-records` does not require sync-prd. When required:

```foundry-invoke
prd-sync validate --repo "{app_folder}" --factory-root "{factory_root}"
```

5. Merge every file the writer touched that is outside the ticket's stated scope into `pr_extras_register` as `{path, reason, step_id}`.
6. Present the DocChangeReport and collect `approve` or `doc_changes`. `doc_changes` is a self-loop on this step.
7. The successful provenance-bound completion records `steps.implement.documentation.report=received`; resolve the gate with `gate resolve`.

**Documentation is never skipped**, including on devops-only or config-only tickets. "Nothing changed" is a DocChangeReport saying so, not a skipped step.

## State keys this step owns

- `steps.implement.documentation.status`
- `steps.implement.documentation.report`
- `steps.implement.documentation.human_approved`
- `steps.implement.documentation.prd_created_or_updated`
- `steps.implement.documentation.sync_prd_ok`
- `pr_extras_register`

Pipeline/result fields such as `model` and `documentation_result` may persist on step evidence (`additionalProperties`); they are not additional owned keys.

## Gate

`human_approval` (`approve_documentation`), satisfied only when `human_approved` is true **and** `report == 'received'`. Blocks `deliver.gate`, `deliver.scope_comment`, and `deliver.ship`.

## Invalid transitions

- **This step cannot run before `implement.code_review` is approved** and, when `config.review.run_before_pr` is enabled, before `implement.pre_pr_review` is approved. `requires` makes `transition` reject early arrivals; `delivery-check` re-asserts evidence.
- Mechanical documentation helpers are CLI commands (`docs pipeline`, `prd-sync`, `knowledge`), not flow step IDs. Parent does not run `docs discover`, `docs audit`, `prd generate`, or `prd validate`.
- Generic publication gate: `publication.required` → `publication.passed` (`DOCUMENTATION_PUBLICATION`; IoT alias `SYNC_PRD` when a PRD changed). When required and not passed, `delivery-check` fails; run `prd-sync validate` and do not clear the flag. `feature-records` does not require sync-prd.
