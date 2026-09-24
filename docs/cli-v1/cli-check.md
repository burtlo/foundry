# check

Status: **draft capability spec**

The `foundry check` command group evaluates entries from the flow registry check catalog in [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml). Checks are observational per [control-plane.md](../workflow-schema-v1/control-plane.md): they report `pass`, `fail`, or `not_applicable` without mutating workflow state. The engine normally evaluates checks at lifecycle hooks; `check eval` exposes the same evaluation for stewards, operators, intake receipts, and eval harnesses. Hub: [cli.md](cli.md).

---

## eval

### Purpose

Run a single catalog check by id. Dispatches by check body type:

| Body | Evaluation |
|---|---|
| `when` | Expression over `config`, `state`, `visit`, `history` ([expressions.md](../workflow-schema-v1/expressions.md)) |
| `command` | Read-only CLI probe (exit `0`/`1`/`2` mapping) |
| `path` | Existence test for `registry:`, `run:`, or `workspace:` path |

Does not append ledger events unless invoked by the engine during a hook.

### Who invokes

| Actor | When |
|---|---|
| engine | Lifecycle hooks (`on_examine`, `on_open`, `on_close`, `on_seal`) |
| steward | Intake workers capture CLI outputs in intake receipt |
| operator | Debug a failing hook |
| eval | Harness reproduces check results |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--check` | yes | Catalog check id (e.g. `validate-manifest`) |
| `--run` | yes* | Run id for state/history namespaces |
| `--visit` | no | Active visit id (default: current open visit) |
| `--flow` | no | Flow registry path (default: bundled `implementation`) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry check eval --check validate-git-clean-execute --run run-2026-09-24-porcelain-003 --json
```

### Sample JSON / exit code

CLI exit code mirrors check result when `--json` is omitted: `0` pass, `1` fail, `2` not_applicable. Evaluation errors exit non-zero with distinct error payload (engine would record `check.errored`).

Pass:

```json
{
  "check_id": "validate-git-clean-execute",
  "result": "pass",
  "body": "command",
  "probe": "foundry git clean-check",
  "output": {"clean": true}
}
```

Fail:

```json
{
  "check_id": "approved-ac-recorded",
  "result": "fail",
  "body": "when",
  "expression": "state.approved_ac_version >= 1",
  "actual": {"approved_ac_version": 0}
}
```

### Used by factory-flow checks / nodes

All catalog checks are referenced from node lifecycle hooks in `factory-flow.yaml`. See mapping table below.

### Cross-links

- [control-plane.md](../workflow-schema-v1/control-plane.md) — check results and policies
- [cli-app.md](cli-app.md), [cli-git.md](cli-git.md), [cli-graph.md](cli-graph.md), [cli-build.md](cli-build.md) — command probe implementations
- [cli-ledger.md](cli-ledger.md) — `query` for history-backed checks

---

## Catalog check mapping

Full check catalog from `factory-flow.yaml` `flow.checks` and its evaluation surface.

| Check id | Body | CLI command or engine expression only |
|---|---|---|
| `validate-manifest` | `command: validate_manifest` | `foundry app validate` (via `check eval` or direct probe) |
| `validate-git-clean-execute` | `command: validate_git_clean_execute` | `foundry git clean-check` |
| `validate-verify-context` | `command: validate_verify_context` | Composite probe: manifest valid, `feature_branch` set, `final_commit_sha` set, execution graph present, required receipts linked ([cli-app.md](cli-app.md), [cli-git.md](cli-git.md), [cli-graph.md](cli-graph.md), [cli-build.md](cli-build.md)) |
| `ensure-execution-graph-reference` | `command: ensure_execution_graph_reference` | `foundry graph ensure-reference` |
| `validate-build-exit` | `command: validate_build_exit` | `foundry build validate-exit` |
| `prior-shape-intake-sealed` | `when` | Engine expression only |
| `prior-examine-sealed` | `when` | Engine expression only |
| `prior-present-sealed` | `when` | Engine expression only |
| `prior-shape-record-sealed` | `when` | Engine expression only |
| `prior-execute-intake-sealed` | `when` | Engine expression only |
| `prior-execute-commit-sealed` | `when` | Engine expression only |
| `prior-verify-intake-sealed` | `when` | Engine expression only |
| `prior-verify-acceptance-sealed` | `when` | Engine expression only |
| `prior-execute-build-sealed` | `when` | Engine expression only |
| `prior-execute-test-sealed` | `when` | Engine expression only |
| `approved-ac-recorded` | `when` | Engine expression only |
| `feature-branch-set` | `when` | Engine expression only |
| `execution-graph-set` | `when` | Engine expression only |
| `final-commit-recorded` | `when` | Engine expression only |
| `review-enabled` | `when` | Engine expression only |
| `acceptance-passed` | `when` | Engine expression only |
| `code-quality-done-or-skipped` | `when` | Engine expression only |
| `code-review-approved` | `when` | Engine expression only |
| `intake-receipt-sealed` | `when` | Engine expression only |
| `agent-receipt-sealed` | `when` | Engine expression only |
| `reshape-within-limit` | `when` | Engine expression only |
| `reexecute-within-limit` | `when` | Engine expression only |
| `reverify-within-limit` | `when` | Engine expression only |

### Nodes referencing command probes

| Check id | Nodes (hook) |
|---|---|
| `validate-manifest` | `shape.intake` (`on_open`), `execute.intake` (`on_open`), `verify.intake` (`on_open`) |
| `validate-git-clean-execute` | `execute.intake` (`on_open`) |
| `validate-verify-context` | `verify.intake` (`on_open`) |
| `ensure-execution-graph-reference` | `execute.plan` (`on_open`) |
| `validate-build-exit` | `execute.build` (`on_seal`) |

---

For CLI mechanics borrowed from earlier prototypes, see [cli-poc-transition.md](cli-poc-transition.md).
