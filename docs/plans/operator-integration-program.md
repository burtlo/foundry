# Operator integration program

Status: **complete**

Phased delivery of production-shaped operator UX on top of the shipped job host and implementation flow runtime.

## Phases

| Phase | Focus | Record | Status |
|------:|-------|--------|--------|
| 0 | Docs truth + operator runbook | [operator-runbook.md](../operator-runbook.md) | **Done** |
| 1 | Host client timeouts for long `run.advance` | [run-advance.md](../cli/run-advance.md), [operator runbook § long advance](../operator-runbook.md#long-run-advance-through-the-host) | **Done** |
| 2 | In-repo Cursor SDK judgment bridge | [judgment-bridge.md](../features/judgment-bridge.md) | **Done** |
| 3 | Background auto-advance daemon on host | [host-auto-advance.md](../features/host-auto-advance.md) | **Done** |
| 4 | Host protocol for TUI (`run.context`, enrichments) | [host-tui-protocol.md](../features/host-tui-protocol.md) | **Done** |
| 5 | Textual `foundry tui` host client | [foundry-tui.md](../features/foundry-tui.md) | **Done** |
| 6 | Integration smoke (bridge + host + shape) | [operator runbook § integration smoke](../operator-runbook.md#integration-smoke) | **Done** |

Delivery plans for phases 3–6 are archived under [plans/archive/](archive/README.md).

**Non-goals:** real deliver phase (terminal remains `deliver.stub`), `foundry init` alias, registry Cursor invoke workflow until bridge + daemon prove judgment path.

## References

- [Operator runbook](../operator-runbook.md)
- [Job host architecture](../concepts/job-host-architecture.md)
- [Agent adapter](../concepts/agent-adapter.md)
- [Implementation flow runtime](../features/implementation-flow-runtime.md)
