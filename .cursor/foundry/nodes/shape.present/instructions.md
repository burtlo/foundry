# Shape presentation

## Goal

Publish the `presentation` artifact and seal the agent receipt evidencing the plan presentation.

## While opened

### 1. Launch the shape-presenter worker

Launch the bound worker with inputs from the context packet:

| Field | Source |
|---|---|
| `subagent_type` | context `worker` (`shape-presenter`) |
| `draft_ac` | `reads.state.draft_ac` |
| `assumptions` | `reads.state.assumptions` |
| `ticket` | `reads.state.ticket` |
| `examination_decisions` | `reads.state.examination_decisions` |
| `clarifying_questions` | `reads.state.clarifying_questions` |

Do not draft presentation markdown before the worker returns — the worker proposes content and a PROCEED or BLOCKED verdict.

### 2. Assemble evidence

Write the worker's full assessment markdown once to `outputs.assessment_path` (e.g. `run:receipts/{visit_id}/assessment.md`).

Build `run:receipts/agent.json` per `registry:schemas/agent-receipt.schema.json` from worker outputs (including `outputs.assessment_path` and short `outputs.summary_markdown`).

### 3. Proceed path (worker verdict PROCEED)

Read the assessment at `outputs.assessment_path` and extract the **Presentation draft** section into `run:artifacts/{visit_id}/presentation.md`. If that section is missing, use the worker's proposed presentation content from the assessment body — still write one canonical `presentation.md`. Seal the **full** `outputs.presented_ac` in the agent receipt (no truncation).

Always patch presentation state from worker outputs before publish:

```foundry-invoke
visit state patch --run "{run_id}" --set '{"presented_ac": "<outputs.presented_ac>", "presentation_artifact_path": "<outputs.presentation_artifact_path>"}' --json
```

```foundry-invoke
artifact publish --run "{run_id}" --visit "{visit_id}" --artifact presentation --source run:artifacts/{visit_id}/presentation.md --json
```

```foundry-invoke
receipt seal --run "{run_id}" --visit "{visit_id}" --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json --json
```

```foundry-invoke
visit transition --run "{run_id}" --visit "{visit_id}" --summary "Shape presentation complete" --json
```

### 4. Blocked path (worker verdict BLOCKED)

Seal the agent receipt only — do **not** publish the presentation or call `transition`:

```foundry-invoke
receipt seal --run "{run_id}" --visit "{visit_id}" --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json --json
```

Explain blockers; when resolved, repeat from step 1.

## Boundaries

- Do not route or name the next node — `transition` requests close only.
- Do not draft or publish `presentation.md` before the worker returns proposed content.
- Do not call `transition` while the worker verdict is BLOCKED.
- Do not call `gate decide` — this is a step, not a gate.
