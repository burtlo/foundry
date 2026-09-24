---
step_id: intake.grill
title: Grill the story for unknowns
subagent: grilling
run_modes: [implementation, analysis]
delivery_gate: false
state_keys:
  - steps.intake.grill.status
  - steps.intake.grill.approved
  - steps.intake.grill.human_approved
  - steps.intake.grill.receipt_id
  - assumptions
  - grilling_decisions
  - grilling_unresolved_count
---

## Purpose

Interrogate the draft story before research or building. Launch a **grilling** Task (craft overlay only). Skipped on the fast lane when `readiness == Ready` and `clarifying_questions_count == 0`.

## Inputs (from parent)

- `draft_ac`, `readiness`, `risk_tier`
- FactoryConfig: `foundry.grilling` (`max_rounds`, `enabled`)
- Open questions from story-writer (via receipt or ticket packet)
- Sealed `{run_dir}/ticket.json` when present

## Parent actions

1. Run `worker launch-packet --state "{state_path}"`.
2. Launch `Task(subagent_type=grilling)` with the returned exact prompt. Worker writes only `craft_staging_path`; parent must not write staging/receipts.
3. Complete using the packet's `craft_staging_path` and `launch_id`.
4. Record `grilling_decisions[]` and `grilling_unresolved_count` from the completed receipt.
5. If clarifying questions remain or unresolved > 0: present them; **STOP** for human answers. Do not self-settle.
6. Human approve: `gate resolve --source human` then `transition --to intake.present_ac`. Engine rejects `--source auto` when `clarifying_questions_count > 0`.
7. Scope changes → `--decision revise_ac` back to `intake.refine`.
8. When unresolved remain, human must `--decision accept_risk` **and** `assumptions` non-empty.

## State keys this step owns

- `steps.intake.grill.status`
- `steps.intake.grill.approved`
- `steps.intake.grill.receipt_id`
- `assumptions`
- `grilling_decisions`
- `grilling_unresolved_count`

## Gate

`human_approval` (`approve_grilling`). Blocks `intake.present_ac`. When grilling ran, assumptions are **forbidden** at AC synthesis — decisions must be explicit.

## Invalid transitions

- `revise_ac` is the only edge back to `intake.refine`.
- Do not answer your own questions and proceed. Unanswered questions require recorded `assumptions` plus human `accept_risk`.
- High-risk tickets with `Needs refinement` must not skip this step.
- Do not hand-write receipts or retry `subagent complete` with a fabricated receipt after `INVALID_RECEIPT`. Relaunch Task or `run block`.
