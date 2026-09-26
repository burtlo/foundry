# graph

Status: **draft capability spec**

The `foundry graph` command group validates and materializes the execution graph (`execution-graph.json`) produced at `execute.plan`. Graph structure follows `execution-graph.schema.json`; publication and consumption rules are in [artifacts.md](../workflow-schema-v1/artifacts.md). Graph identity is tracked in `state.execution_graph_id` and referenced by build and verify nodes. Hub: [cli.md](cli.md).

---

## validate

### Purpose

Validate an execution graph file against schema and semantic rules: work item topology, AC references, owner routes, dependency closure, and alignment with `approved_ac` / digest when provided.

### Who invokes

| Actor | When |
|---|---|
| steward | Planner after composing graph at `execute.plan` |
| operator | Debug graph JSON outside a run |
| eval | Harness graph fixture checks |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--file` | yes | Graph path (`run:` or workspace path) |
| `--run` | no | Run id for state-backed AC alignment |
| `--approved-ac` | no | Explicit AC document path for cross-check |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry graph validate --file run:artifacts/v-012/execution-graph.json --run run-2026-09-24-porcelain-003 --json
```

### Sample JSON / exit code

Exit `0` when valid. Exit `1` on validation errors.

```json
{
  "valid": true,
  "graph_id": "eg-2026-09-24-003",
  "work_item_count": 3,
  "topology": "multi_worker",
  "errors": []
}
```

### Used by factory-flow checks / nodes

| Node / check | Role |
|---|---|
| `execute.plan` | Planner validates before `artifact.publish` |
| `execution-graph-set` | State check after graph id recorded |
| `execute.build` | `on_examine` requires graph in state |

### Cross-links

- [cli-graph.md](cli-graph.md) — `ensure-reference`
- [cli-artifact.md](cli-artifact.md) — publish `execution-graph` artifact
- [validation.md](../workflow-schema-v1/validation.md) — semantic validation rules

---

## ensure-reference

### Purpose

Ensure a durable execution graph reference exists beside run state (`run:execution-graph.json`) and sync `state.execution_graph_id`. If the planner published a visit-scoped artifact only, copies or links to the canonical run-level path. Read-only with respect to work-item completion; does not mutate graph item status.

Catalog probe: `ensure-execution-graph-reference` (`command: ensure_execution_graph_reference`).

### Who invokes

| Actor | When |
|---|---|
| engine | `execute.plan` `on_open` → `ensure-execution-graph-reference` |
| steward | Planner step when graph file already exists from prior cycle |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--file` | no | Explicit graph source (default: nearest published artifact) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry graph ensure-reference --run run-2026-09-24-porcelain-003 --json
```

### Sample JSON / exit code

Check probe: exit `0` = pass, `1` = fail, `2` = not_applicable.

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "graph_id": "eg-2026-09-24-003",
  "canonical_path": "run:execution-graph.json",
  "source_visit_id": "v-012",
  "synced": true
}
```

### Used by factory-flow checks / nodes

| Node / check | Hook | Role |
|---|---|---|
| `ensure-execution-graph-reference` | catalog `command: ensure_execution_graph_reference` | Probe body |
| `execute.plan` | `on_open` → `ensure-execution-graph-reference` | Canonical graph path before planner work |
| `execute.plan` | `on_seal` → `execution-graph-set` | Graph id must be in state |
| `execute.build` | `on_examine` → `execution-graph-set` | Build requires graph |

### Cross-links

- [cli-check.md](cli-check.md) — `check eval --check ensure-execution-graph-reference`
- [cli-build.md](cli-build.md) — `validate-exit` reads graph completion
- [graph.md](../workflow-schema-v1/graph.md) — node routing (distinct from execution graph)

---

For CLI mechanics borrowed from earlier prototypes, see [cli-poc-transition.md](cli-poc-transition.md).
