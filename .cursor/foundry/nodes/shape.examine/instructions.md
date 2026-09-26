# Shape examination

## Goal

Seal the agent receipt evidencing examination conversation and draft acceptance criteria.

## While opened

### 1. Review ticket and conduct examination

Read the sealed intake `ticket` from `reads.state.ticket` in the context packet. Ask clarifying questions per `allow.user.ask`. Patch examination state as the conversation progresses:

```foundry-invoke
visit state patch --run "{run_id}" --set '{"draft_ac": "...", "open_clarifying_questions_count": 0}' --json
```

Track `clarifying_questions`, `assumptions`, `examination_decisions`, `questions_asked_total`, and `examination_round` through state patches.

### 2. Assemble evidence

```foundry-invoke
ledger show --run "{run_id}" --types check.recorded --json
```

Build `run:receipts/agent.json` per `registry:schemas/agent-receipt.schema.json` from steward work and ledger `check.recorded` events for `{visit_id}`.

### 3. Seal and transition

```foundry-invoke
receipt seal --run "{run_id}" --visit "{visit_id}" --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json --json
```

```foundry-invoke
visit transition --run "{run_id}" --visit "{visit_id}" --summary "Shape examination complete" --json
```

## Boundaries

- Do not route or name the next node — `transition` requests close only.
- Do not launch a worker — steward conducts the examination conversation.
- Do not publish artifacts — this node produces no work artifacts.
- Do not pass `checks[]` to any subagent; build receipt checks from ledger events for this visit.
- Do not re-run intake manifest validation — the engine recorded it on the ancestor visit.
