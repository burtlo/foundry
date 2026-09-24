# Post-run learning (Phase L)

Offline record written by `run finalize-learning`. Stewards must **not** load this into the next chat.

See `schemas/packets/learning-record.schema.json` and `docs/seam-packet-catalog.md`.

## Required at `run complete` (MVP)

- outcome card: status, pr_url, duration_ms, interaction_mode, issue_key, app_folder
- rework counters
- failure_class_distribution
- gate_source_histogram (human vs auto)

## Best-effort (populate when available)

- auto_gate_overturns
- session_boundaries / handoff count
- seam_friction
- assumption_ledger (from grill accept_risk / low confidence)
- critic_tags (normalized; not full Bugbot prose)
- seams / reliability_in_scope
- foundry_git_sha, packet size hints
- knowledge suggest accept/reject events

## Explicitly deferred

- Full transcript storage

## Outputs

| File | Role |
|------|------|
| `{run_dir}/learning_record.json` | Machine record |
| `{run_dir}/learning_review.md` | Short human scannable summary |
| `{run_dir}/outcomes.jsonl` | Append-only PR check and merge observations |
| `{run_dir}/learning_record.observed.json` | Learning record enriched with the latest observation |

Run `outcome observe --state "{state_path}"` from CI or a scheduled authenticated
job. It is idempotent for an unchanged GitHub snapshot and does not block
`run complete`.

## Gap dispositions

| Gap | Disposition |
|-----|-------------|
| Human overturn of auto gates | Accepted — MVP histogram + overturns when detectable |
| Session / steward boundaries | Best-effort — handoff count from events |
| Model identity per launch | Deferred — if Cursor exposes model id later |
| AC churn after freeze | Best-effort — version bumps in events |
| Work-item estimate vs actual | Deferred |
| Rework cause linkage | Best-effort — rework edges in events |
| Critic finding taxonomy | Best-effort tags only |
| Integration seam flags | Best-effort null until detector exists |
| PR outcome post-ship | Accepted — offline `outcome observe` via authenticated `gh` |
| Abandoned reason | Accepted — `run abandon` |
| Profile + factory SHA | Accepted — profile hash required; git sha best-effort |
| Builder packet size | Accepted — full-packet utilization recorded in launch meta and receipts |
| Knowledge suggest accept/reject | Deferred until promote CLI exists |
