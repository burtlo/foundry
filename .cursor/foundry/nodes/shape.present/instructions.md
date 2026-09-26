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

```foundry-invoke
ledger show --run "{run_id}" --types check.recorded --json
```

Build `run:receipts/agent.json` per `registry:schemas/agent-receipt.schema.json` from worker outputs and ledger `check.recorded` events for `{visit_id}`.

### 3. Proceed path (worker verdict PROCEED)

Extract the **Presentation draft** section from the worker's `outputs.summary_markdown` and write it once to `run:artifacts/{visit_id}/presentation.md`.

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
- Do not pass `checks[]` to the worker; build receipt checks from ledger events for this visit.
- Do not draft or publish `presentation.md` before the worker returns proposed content.
- Do not call `transition` while the worker verdict is BLOCKED.
- Do not call `gate decide` — this is a step, not a gate.
