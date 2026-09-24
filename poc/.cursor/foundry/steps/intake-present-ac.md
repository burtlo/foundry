---
step_id: intake.present_ac
title: Present acceptance criteria
subagent: null
run_modes: [implementation, analysis]
delivery_gate: false
state_keys:
  - steps.intake.present_ac.status
  - steps.intake.present_ac.human_approved
  - steps.intake.present_ac.gate_decision
  - presented_ac
---

## Purpose

Present the synthesized acceptance criteria (implementation) or deliverable checklist (analysis) in full before scope freeze. This is the **presentation turn** of the two-turn gate — unchanged v1 semantics, now a dedicated step.

## Inputs (from parent)

- `draft_ac` from `intake.refine` (merged with grilling decisions when grilling ran)
- `readiness`, `config.story_writer`
- On analysis runs: `config.analysis`

## Parent actions

1. Merge `draft_ac` with any AC changes from `grilling_decisions`. When grilling ran, **forbidden**: silent assumptions — every open question must be a recorded decision or explicit assumption before synthesis.
2. Copy the merged list into `presented_ac` (full `{id, text, source}` objects).
3. Present **in full** following `.cursor/foundry/templates/story-refinement-presentation-step.md` sections **1–7** — every section, every criterion, no summarising. Use `approve_refined_story` on implementation runs and `approve_deliverables` on analysis runs.
4. **STOP.** Do not call AskQuestion on the presentation turn.
5. On the **next** turn: set `steps.intake.present_ac.human_approved=true`, `steps.intake.present_ac.gate_decision`, then `transition --to intake.approve_ac`.
6. Re-present in full if any criterion was skipped or summarised.

## Launch packet (pass to Task; not parent work)

None. Parent owns presentation.

## State keys this step owns

- `steps.intake.present_ac.status`
- `steps.intake.present_ac.human_approved`
- `steps.intake.present_ac.gate_decision`
- `presented_ac`

## Gate

`two_turn_stop`. Satisfied only when `steps.intake.present_ac.human_approved` is true. Blocks `intake.approve_ac`, `plan.research`, and `analysis.research`.

## Invalid transitions

- Presenting and asking for approval in the same turn does not satisfy the gate.
- Do not bump `approved_ac_version` here — that happens at `intake.approve_ac`.
