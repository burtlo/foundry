# Shape record

## Goal

Publish the `plan` artifact, freeze `approved_ac`, and seal the agent receipt evidencing the record step.

## While opened

### 1. Launch the shape-recorder worker

Launch the bound worker with inputs from the context packet:

| Field | Source |
|---|---|
| `subagent_type` | context `worker` (`shape-recorder`) |
| `presented_ac` | `reads.state.presented_ac` |
| `presentation_artifact_path` | `reads.state.presentation_artifact_path` |
| `presentation` | `reads.artifacts` — Artifacts row `shape.present.presentation` |

Do not draft plan markdown before the worker returns — the worker proposes content and a PROCEED or BLOCKED verdict.

### 2. Assemble evidence

```foundry-invoke
ledger show --run "{run_id}" --types check.recorded --json
```

Build `run:receipts/agent.json` per `registry:schemas/agent-receipt.schema.json` from worker outputs and ledger `check.recorded` events for `{visit_id}`.

### 3. Proceed path (worker verdict PROCEED)

Extract the **Plan draft** section from the worker's `outputs.summary_markdown` and write it once to both `run:artifacts/{visit_id}/plan.md` and `workspace:plan.md`.

Patch record state from worker outputs before publish:

```foundry-invoke
visit state patch --run "{run_id}" --set '{"approved_ac": "<outputs.approved_ac>", "approved_ac_version": <outputs.plan_version>, "approved_ac_digest": "<outputs.approved_ac_digest>", "plan_path": "<outputs.plan_path>", "plan_version": <outputs.plan_version>}' --json
```

```foundry-invoke
artifact publish --run "{run_id}" --visit "{visit_id}" --artifact plan --source run:artifacts/{visit_id}/plan.md --json
```

```foundry-invoke
receipt seal --run "{run_id}" --visit "{visit_id}" --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json --json
```

```foundry-invoke
visit transition --run "{run_id}" --visit "{visit_id}" --summary "Shape record complete" --json
```

### 4. Blocked path (worker verdict BLOCKED)

Seal the agent receipt only — do **not** publish the plan or call `transition`:

```foundry-invoke
receipt seal --run "{run_id}" --visit "{visit_id}" --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json --json
```

Explain blockers; when resolved, repeat from step 1.

## Boundaries

- Do not route or name the next node — `transition` requests close only.
- Do not pass `checks[]` to the worker; build receipt checks from ledger events for this visit.
- Do not draft or publish `plan.md` before the worker returns proposed content.
- Do not call `transition` while the worker verdict is BLOCKED.
- Do not call `gate decide` — this is a step, not a gate.
