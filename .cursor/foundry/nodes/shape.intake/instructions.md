# Shape intake

## Goal

Publish the `ticket` artifact and seal intake and agent receipts for this visit.

## While opened

### 1. Confirm scope with the user

Confirm the work request matches `work_prompt` and the application repo root. If `reads.state.app_folder` is unset, resolve with the user (default: `reads.config.workspace`). Patch when it changes:

```foundry-invoke
visit state patch --run "{run_id}" --set '{"app_folder": "<resolved path>"}' --json
```

### 2. Launch the intake checker worker

Launch the bound worker with resolved inputs only:

| Field | Source |
|---|---|
| `subagent_type` | context `worker` (`intake-checker.shape`) |
| `app_folder` | `reads.state.app_folder` after patch |
| `work_prompt` | `work_prompt` from `/craft-shape` |

Do not draft ticket fields before the worker returns — the worker proposes ticket values and a PROCEED or BLOCKED verdict.

### 3. Assemble evidence

```foundry-invoke
ledger show --run "{run_id}" --types check.recorded --json
```

Build receipt drafts filtered to `{visit_id}`:

- `run:receipts/intake.json` per `registry:schemas/intake-receipt.schema.json` — map worker verdict to `status` (`PROCEED` → `passed`, `BLOCKED` → `blocked`); `checks[]` from ledger; worker assessment per schema.
- `run:receipts/agent.json` per `registry:schemas/agent-receipt.schema.json` — worker outputs per schema and contract.

Write `run:ticket.json` once from the worker's proposed ticket fields per `registry:schemas/ticket.schema.json`.

### 4. Proceed path (worker verdict PROCEED)

```foundry-invoke
artifact publish --run "{run_id}" --visit "{visit_id}" --artifact ticket --source run:ticket.json --json
```

```foundry-invoke
receipt seal --run "{run_id}" --visit "{visit_id}" --schema registry:schemas/intake-receipt.schema.json --file run:receipts/intake.json --json
```

```foundry-invoke
receipt seal --run "{run_id}" --visit "{visit_id}" --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json --json
```

```foundry-invoke
visit transition --run "{run_id}" --visit "{visit_id}" --summary "Shape intake complete" --json
```

### 5. Blocked path (worker verdict BLOCKED)

Seal receipts only — do **not** write `run:ticket.json`, publish the ticket, or call `transition`:

```foundry-invoke
receipt seal --run "{run_id}" --visit "{visit_id}" --schema registry:schemas/intake-receipt.schema.json --file run:receipts/intake.json --json
```

```foundry-invoke
receipt seal --run "{run_id}" --visit "{visit_id}" --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json --json
```

Explain blockers; when resolved, repeat from step 2.
## Boundaries

- Do not route or name the next node — `transition` requests close only.
- Do not pass `checks[]` to the worker; build receipt checks from ledger events for this visit.
- Do not draft or publish `ticket.json` before the worker returns proposed fields.
- Do not call `transition` while the worker verdict is BLOCKED.
- Do not re-run manifest validation — the engine recorded it at open.
