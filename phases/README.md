# Job host — phased delivery (Phases 0–7)

Status: Phases 0–7 implemented per linked phase docs; host protocol and Shape user path are usable with stub agent adapter. Remaining host gaps: full materialized-state replay from events, async HTTP agent without auto-accept, TUI/web, and broader operations executor coverage.

**Architecture:** [Job host target architecture](../docs/concepts/job-host-architecture.md)

**After Phase 6:** workflow graph completion and gap closure live under [docs/plans](../docs/plans/) — start with [orchestrator-brief.md](../docs/plans/orchestrator-brief.md) and [shape-execute-verify-gap-closure-plan.md](../docs/plans/shape-execute-verify-gap-closure-plan.md).

| Order | Phase | Expected proof |
|---:|---|---|
| 0 | [Baseline and responsibility inventory](00-baseline.md) | Each Shape instruction has an owner and current behavior is tested. |
| 1 | [Extract deterministic Shape work](01-shape-extraction.md) | Intake advances without an agent; Examination contains judgment only. |
| 2 | [Durable advancement and recovery](02-run-engine.md) | A fresh process resumes a run safely at a declared boundary. |
| 3 | [Persistent local job host](03-job-host.md) — **complete** | A run outlives its CLI client and remains inspectable. |
| 4 | [Model API connection](04-agent-connection.md) — **complete** | Examination uses a validated model result through the host. |
| 5 | [User CLI for Shape](05-shape-cli.md) — **complete** | A developer can initialize and finish Shape through user commands. |
| 6 | [Execute and Verify](06-execute-verify.md) — **complete** (skeleton; see gap plan) | Explicit start and supervision for execution and verification. |
| 7 | [Append-only ledger](07-append-only-ledger.md) — **complete** | Ledger events append to `ledger.jsonl` before snapshot commit; migration and recovery tested. |

## Delivery rules

Finish each phase's acceptance criteria before relying on its contracts in the next phase. Keep compatibility wrappers only as long as tests and migration require them. Update hand-maintained concepts and generated docs affected by each change. Migrate existing run data explicitly; never silently reinterpret old state. Preserve unrelated working-tree changes.

Phases 0–2 establish the semantic boundary and durable engine. Phase 3 adds the persistent host. Phase 4 adds model calls. Phase 5 makes Shape usable through the CLI. Phase 6 expands the path to Execute and Verify. TUI, web UI, distributed queues, and a general agent tool platform are outside this sequence.

## Follow-on

**P7 — append-only ledger:** Implemented — see [07-append-only-ledger.md](07-append-only-ledger.md). Host-side ledger compaction and full event-sourced replay of visit state remain future work.
