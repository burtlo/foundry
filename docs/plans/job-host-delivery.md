# Foundry job host: ordered delivery plan

Status: proposed. The [architecture and contracts](job-host-architecture.md) define the target; the phase documents below define implementation work. Target commands and schemas are not implemented yet.

| Order | Phase | Expected proof |
|---:|---|---|
| 0 | [Baseline and responsibility inventory](phases/00-baseline.md) | Each Shape instruction has an owner and current behavior is tested. |
| 1 | [Extract deterministic Shape work](phases/01-shape-extraction.md) | Intake advances without an agent; Examination contains judgment only. |
| 2 | [Durable advancement and recovery](phases/02-run-engine.md) | A fresh process resumes a run safely at a declared boundary. |
| 3 | [Persistent local job host](phases/03-job-host.md) | A run outlives its CLI client and remains inspectable. |
| 4 | [Model API connection](phases/04-agent-connection.md) | Examination uses a validated model result through the host. |
| 5 | [User CLI for Shape](phases/05-shape-cli.md) | A developer can initialize and finish Shape through user commands. |
| 6 | [Execute and Verify](phases/06-execute-verify.md) | A developer explicitly starts and supervises execution and verification. |

## Delivery rules

Finish each phase's acceptance criteria before relying on its contracts in the next phase. Keep compatibility wrappers only as long as tests and migration require them. Update hand-maintained concepts and generated docs affected by each change. Migrate existing run data explicitly; never silently reinterpret old state. Preserve unrelated working-tree changes.

Phases 0–2 establish the semantic boundary and durable engine. Phase 3 adds the persistent host. Phase 4 adds model calls. Phase 5 makes Shape usable through the CLI. Phase 6 expands the path to Execute and Verify. TUI, web UI, distributed queues, and a general agent tool platform are outside this plan.
