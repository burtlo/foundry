# Foundry CLI reference

Generated from `foundry doc build` / `foundry dev docs`. Mechanical flags come from argparse; summaries and links are annotated in `foundry_cli/cli_docgen.py`.

Entry point: [foundry.py](../../.cursor/foundry/cli/foundry.py)

## Global flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--workspace` | no | . | Application repository root |
| `--registry` | no | — | Foundry bundle root (.cursor/foundry) |
| `--json` | no | false | Emit JSON response envelope |


## Operator curriculum

Default `foundry -h` and `foundry help` list only these commands, grouped in journey order (metadata: `foundry_cli/help_catalog.py`). Use `foundry help -a` for maintainer and engine commands.

### Set up the workspace

| Command | Summary | Reference |
|---|---|---|
| `config` | Foundry registry config commands | [config init](config-init.md), [config validate](config-validate.md) |
| `app` | Application manifest bootstrap commands | [app discover](app-discover.md), [app init](app-init.md), [app validate](app-validate.md) |

### Local Foundry

| Command | Summary | Reference |
|---|---|---|
| `up` | Start or reconcile bridge and host for this workspace | [up](up.md) |
| `down` | Stop host and judgment bridge started or reconciled by foundry up | [down](down.md) |

### Start and watch runs

| Command | Summary | Reference |
|---|---|---|
| `shape` | Create a run from a shape request and advance into Shape | [shape](shape.md) |
| `runs` | List workspace runs (phase, node, status, wait) | [runs](runs.md) |
| `status` | Show run status (default: sole active run) | [status](status.md) |
| `attach` | Show run snapshot and stream ledger events | [attach](attach.md) |

### When the run needs you

| Command | Summary | Reference |
|---|---|---|
| `answer` | Submit clarifying answers when wait.kind is user_input | [answer](answer.md) |
| `decide` | Submit a decision at the active user gate | [decide](decide.md) |
| `start` | Explicit Shape → Execute authorization at execute.start | [start](start.md) |

### Recover or stop a run

| Command | Summary | Reference |
|---|---|---|
| `retry` | Retry a recoverable halted or errored run | [retry](retry.md) |
| `cancel` | Stop a run with a recorded reason | [cancel](cancel.md) |

## All commands

Complete leaf-command reference (listed and unlisted).

| Capability | Command | Status | Reference |
|---|---|---|---|
| `answer` | `answer` | implemented | [answer](answer.md) |
| `app.discover` | `app discover` | implemented | [app-discover](app-discover.md) |
| `app.init` | `app init` | implemented | [app-init](app-init.md) |
| `app.validate` | `app validate` | implemented | [app-validate](app-validate.md) |
| `artifact.publish` | `artifact publish` | implemented | [artifact-publish](artifact-publish.md) |
| `attach` | `attach` | implemented | [attach](attach.md) |
| `bridge.start` | `bridge start` | implemented | [bridge-start](bridge-start.md) |
| `cancel` | `cancel` | implemented | [cancel](cancel.md) |
| `catalog.build` | `catalog build` | implemented | [catalog-build](catalog-build.md) |
| `cli.resolve` | `cli resolve` | implemented | [cli-resolve](cli-resolve.md) |
| `config.init` | `config init` | implemented | [config-init](config-init.md) |
| `config.validate` | `config validate` | implemented | [config-validate](config-validate.md) |
| `decide` | `decide` | implemented | [decide](decide.md) |
| `dev.acceptance` | `dev acceptance` | implemented | [dev-acceptance](dev-acceptance.md) |
| `dev.all` | `dev all` | implemented | [dev-all](dev-all.md) |
| `dev.docs` | `dev docs` | implemented | [dev-docs](dev-docs.md) |
| `dev.engine-matrix` | `dev engine-matrix` | implemented | [dev-engine-matrix](dev-engine-matrix.md) |
| `dev.unit` | `dev unit` | implemented | [dev-unit](dev-unit.md) |
| `doc.build` | `doc build` | implemented | [doc-build](doc-build.md) |
| `down` | `down` | implemented | [down](down.md) |
| `gate.decide` | `gate decide` | implemented | [gate-decide](gate-decide.md) |
| `help` | `help` | implemented | [help](help.md) |
| `host.logs` | `host logs` | implemented | [host-logs](host-logs.md) |
| `host.run` | `host run` | implemented | [host-run](host-run.md) |
| `host.start` | `host start` | implemented | [host-start](host-start.md) |
| `host.status` | `host status` | implemented | [host-status](host-status.md) |
| `host.stop` | `host stop` | implemented | [host-stop](host-stop.md) |
| `ledger.show` | `ledger show` | implemented | [ledger-show](ledger-show.md) |
| `receipt.seal` | `receipt seal` | implemented | [receipt-seal](receipt-seal.md) |
| `retry` | `retry` | implemented | [retry](retry.md) |
| `run.advance` | `run advance` | implemented | [run-advance](run-advance.md) |
| `run.agent.submit` | `run agent submit` | implemented | [run-agent-submit](run-agent-submit.md) |
| `run.archive` | `run archive` | implemented | [run-archive](run-archive.md) |
| `run.context` | `run context` | implemented | [run-context](run-context.md) |
| `run.create` | `run create` | implemented | [run-create](run-create.md) |
| `run.events` | `run events` | implemented | [run-events](run-events.md) |
| `run.get` | `run get` | implemented | [run-get](run-get.md) |
| `run.list` | `run list` | implemented | [run-list](run-list.md) |
| `run.recover` | `run recover` | implemented | [run-recover](run-recover.md) |
| `runs` | `runs` | implemented | [runs](runs.md) |
| `shape` | `shape` | implemented | [shape](shape.md) |
| `start` | `start` | implemented | [start](start.md) |
| `status` | `status` | implemented | [status](status.md) |
| `tui` | `tui` | implemented | [tui](tui.md) |
| `up` | `up` | implemented | [up](up.md) |
| `visit.examine.complete` | `visit examine complete` | implemented | [visit-examine-complete](visit-examine-complete.md) |
| `visit.intake.complete` | `visit intake complete` | implemented | [visit-intake-complete](visit-intake-complete.md) |
| `visit.plan.complete` | `visit plan complete` | implemented | [visit-plan-complete](visit-plan-complete.md) |
| `visit.present.complete` | `visit present complete` | implemented | [visit-present-complete](visit-present-complete.md) |
| `visit.record.complete` | `visit record complete` | implemented | [visit-record-complete](visit-record-complete.md) |
| `visit.state.patch` | `visit state patch` | implemented | [visit-state-patch](visit-state-patch.md) |
| `visit.transition` | `visit transition` | implemented | [visit-transition](visit-transition.md) |

## See also

- [Workflow concepts index](../concepts/README.md)
- [Engine procedure](../concepts/engine.md)
- [Ledger and run persistence](../concepts/run-record.md)
- [Reads and allow (steward capabilities)](../concepts/capabilities.md)
