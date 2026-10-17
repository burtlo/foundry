# Run block visibility — why is this run stuck?

Status: **open** — [spec](spec.md) approved (2026-10-16). [Implementation map](implementation.md) ready for orchestration (P1–P5).

| Artifact | Description |
|----------|-------------|
| [retro.md](retro.md) | Operator experience: any parked node hides `status_reason` and findings; the main feed should show the block and the lawful actions |
| [spec.md](spec.md) | Approved specification (2026-10-16): one generic parked-run card as the last main-feed entry, full `foundry status` explanation plus next command, Needs **—** while an agent runs |
| [implementation.md](implementation.md) | **Canonical** — deltas, work packages (P1–P5), verifier hooks, build order |

Related: [cli-operator-ux/](../cli-operator-ux/) (porcelain status, attach, operator history); [implementation-flow-runtime.md](../../features/implementation-flow-runtime.md) (blocked intake operator wait, T3/T4); [operator-runbook.md](../../operator-runbook.md).
