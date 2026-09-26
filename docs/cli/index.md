# Foundry CLI reference

Generated from `foundry doc build` / `foundry dev docs`. Mechanical flags come from argparse; summaries and links are annotated in `foundry_cli/cli_docgen.py`.

Entry point: [foundry.py](../../.cursor/foundry/cli/foundry.py)

## Global flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--workspace` | no | . | Application repository root |
| `--registry` | no | — | Foundry bundle root (.cursor/foundry) |
| `--json` | no | false | Emit JSON response envelope |


## Commands

| Capability | Command | Status | Reference |
|---|---|---|---|
| `app.discover` | `app discover` | implemented | [app-discover](app-discover.md) |
| `app.init` | `app init` | implemented | [app-init](app-init.md) |
| `app.validate` | `app validate` | implemented | [app-validate](app-validate.md) |
| `artifact.publish` | `artifact publish` | implemented | [artifact-publish](artifact-publish.md) |
| `catalog.build` | `catalog build` | implemented | [catalog-build](catalog-build.md) |
| `cli.resolve` | `cli resolve` | implemented | [cli-resolve](cli-resolve.md) |
| `dev.acceptance` | `dev acceptance` | implemented | [dev-acceptance](dev-acceptance.md) |
| `dev.all` | `dev all` | implemented | [dev-all](dev-all.md) |
| `dev.docs` | `dev docs` | implemented | [dev-docs](dev-docs.md) |
| `dev.unit` | `dev unit` | implemented | [dev-unit](dev-unit.md) |
| `doc.build` | `doc build` | implemented | [doc-build](doc-build.md) |
| `gate.decide` | `gate decide` | implemented | [gate-decide](gate-decide.md) |
| `ledger.show` | `ledger show` | implemented | [ledger-show](ledger-show.md) |
| `receipt.seal` | `receipt seal` | implemented | [receipt-seal](receipt-seal.md) |
| `run.context` | `run context` | implemented | [run-context](run-context.md) |
| `run.create` | `run create` | implemented | [run-create](run-create.md) |
| `visit.state.patch` | `visit state patch` | implemented | [visit-state-patch](visit-state-patch.md) |
| `visit.transition` | `visit transition` | implemented | [visit-transition](visit-transition.md) |

## See also

- [Workflow concepts index](../concepts/README.md)
- [Engine procedure](../concepts/engine.md)
- [Ledger and run persistence](../concepts/run-record.md)
- [Reads and allow (steward capabilities)](../concepts/capabilities.md)
