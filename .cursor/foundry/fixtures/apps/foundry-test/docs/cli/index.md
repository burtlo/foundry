# Foundry CLI reference

Generated from `foundry doc build` / `foundry dev docs`. Mechanical flags come from argparse; summaries and links are annotated in `foundry_cli/cli_docgen.py`.

Entry point: [foundry.py](../../../../../cli/.cursor/foundry/cli/foundry.py)

## Global flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--workspace` | no | . | Application repository root |
| `--registry` | no | — | Foundry bundle root (.cursor/foundry) |
| `--json` | no | false | Emit JSON response envelope |


## Commands

| Capability | Command | Status | Reference |
|---|---|---|---|
| `answer` | `answer` | implemented | [answer](answer.md) |
| `app.discover` | `app discover` | implemented | [app-discover](app-discover.md) |
| `app.init` | `app init` | implemented | [app-init](app-init.md) |
| `app.validate` | `app validate` | implemented | [app-validate](app-validate.md) |
| `artifact.publish` | `artifact publish` | implemented | [artifact-publish](artifact-publish.md) |
| `attach` | `attach` | implemented | [attach](attach.md) |
| `cancel` | `cancel` | implemented | [cancel](cancel.md) |
| `catalog.build` | `catalog build` | implemented | [catalog-build](catalog-build.md) |
| `cli.resolve` | `cli resolve` | implemented | [cli-resolve](cli-resolve.md) |
| `config.init` | `config init` | implemented | [config-init](config-init.md) |
| `config.validate` | `config validate` | implemented | [config-validate](config-validate.md) |
| `decide` | `decide` | implemented | [decide](decide.md) |
| `dev.acceptance` | `dev acceptance` | implemented | [dev-acceptance](dev-acceptance.md) |
| `dev.all` | `dev all` | implemented | [dev-all](dev-all.md) |
| `dev.docs` | `dev docs` | implemented | [dev-docs](dev-docs.md) |
| `dev.unit` | `dev unit` | implemented | [dev-unit](dev-unit.md) |
| `doc.build` | `doc build` | implemented | [doc-build](doc-build.md) |
| `gate.decide` | `gate decide` | implemented | [gate-decide](gate-decide.md) |
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
| `visit.examine.complete` | `visit examine complete` | implemented | [visit-examine-complete](visit-examine-complete.md) |
| `visit.intake.complete` | `visit intake complete` | implemented | [visit-intake-complete](visit-intake-complete.md) |
| `visit.present.complete` | `visit present complete` | implemented | [visit-present-complete](visit-present-complete.md) |
| `visit.state.patch` | `visit state patch` | implemented | [visit-state-patch](visit-state-patch.md) |
| `visit.transition` | `visit transition` | implemented | [visit-transition](visit-transition.md) |

## See also

- [Workflow concepts index](../../../../../cli/docs/concepts/README.md)
- [Engine procedure](../../../../../cli/docs/concepts/engine.md)
- [Ledger and run persistence](../../../../../cli/docs/concepts/run-record.md)
- [Reads and allow (steward capabilities)](../../../../../cli/docs/concepts/capabilities.md)
