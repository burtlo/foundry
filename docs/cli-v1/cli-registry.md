# registry

Status: **draft capability spec**

The `foundry` authoring commands validate workflow definitions, JSON schemas, and CLI capability registration. They are `foundry flow`, `foundry schema`, `foundry registry`, and `foundry cli`. These commands are for **authoring and CI**. They do not run per-visit workflow logic. Structural rules are in [validation.md](../workflow-schema-v1/validation.md); the reference registry instance is [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml).

---

## flow validate

### Purpose

Semantic validation of a flow registry YAML: unique ids, reachability, connection selectors, check references, artifact declarations, gate compatibility, and expression parsing. Complements JSON Schema structural validation.

### Who invokes

| Actor | When |
|---|---|
| operator | Local authoring loop |
| eval | CI `Foundry Flow Check` workflow |
| engine | Pre-load safety check (optional) |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--flow` | no | Registry path (default: bundled `factory-flow.yaml`) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry flow validate --flow registry:.cursor/foundry/flows/factory-flow.yaml --json
```

### Sample JSON / exit code

Exit `0` when valid. Exit `1` on semantic errors.

```json
{
  "valid": true,
  "flow_id": "implementation",
  "node_count": 24,
  "connection_count": 31,
  "check_count": 28,
  "errors": []
}
```

### Used by factory-flow checks / nodes

| Node / check | Role |
|---|---|
| — | Authoring/CI only; not referenced from runtime hooks |

### Cross-links

- [registry.md](../workflow-schema-v1/registry.md) — conforming registry example
- [validation.md](../workflow-schema-v1/validation.md) — structural vs semantic layers
- [graph.md](../workflow-schema-v1/graph.md) — routing invariants validated here

---

## flow diagram

### Purpose

Generate a Mermaid diagram from the flow registry for documentation and drift detection. `--check` compares output to a committed diagram file when used in CI.

### Who invokes

| Actor | When |
|---|---|
| operator | Refresh flow documentation |
| eval | CI diagram drift check |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--flow` | no | Registry path |
| `--out` | no | Output file path (default: stdout) |
| `--check` | no | Fail if `--out` differs from generated content |
| `--json` | no | Emit metadata only |

### Sample invocation

```text
foundry flow diagram --flow registry:.cursor/foundry/flows/factory-flow.yaml --out docs/workflow-schema-v1/implementation-flow.mmd --check
```

### Sample JSON / exit code

With `--check`, exit `0` when diagram matches; exit `1` on drift. With `--json`:

```json
{
  "flow_id": "implementation",
  "node_count": 24,
  "output_path": "docs/workflow-schema-v1/implementation-flow.mmd",
  "check": true,
  "matched": true
}
```

### Used by factory-flow checks / nodes

| Node / check | Role |
|---|---|
| — | Authoring/CI only |

### Cross-links

- [flow validate](#flow-validate) — validate before diagram generation
- [v1-spec.md](../v1-spec.md) — product phase diagram

---

## schema validate

### Purpose

Validate a JSON or YAML instance file against a named JSON Schema from the registry bundle (`registry:schemas/*.schema.json`).

### Who invokes

| Actor | When |
|---|---|
| operator | Manifest, receipt, or state fixture validation |
| eval | Schema regression tests |
| steward | Receipt sealing validates against declared schema |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--file` | yes | Instance path |
| `--schema` | yes | Schema path (`registry:schemas/...`) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry schema validate --file workspace:.foundry/app.yaml --schema registry:schemas/app-manifest.schema.json --json
```

### Sample JSON / exit code

Exit `0` when valid. Exit `1` on schema violations.

```json
{
  "valid": true,
  "schema": "registry:schemas/app-manifest.schema.json",
  "file": "workspace:.foundry/app.yaml",
  "errors": []
}
```

### Used by factory-flow checks / nodes

| Node / check | Role |
|---|---|
| Receipt schemas | `intake-receipt-sealed`, `agent-receipt-sealed` compare `registry:schemas/...` paths |
| `state_schema` | Flow registry `factory-run-state.schema.json` |

### Cross-links

- [cli-app.md](cli-app.md) — manifest validation
- [cli-receipt.md](cli-receipt.md) — receipt schema sealing
- [artifacts.md](../workflow-schema-v1/artifacts.md) — artifact `schema` field

---

## registry validate

### Purpose

Validate the entire Foundry registry bundle: flow YAML, schemas, steps, agents, contracts, and cross-references (`registry:` paths resolve). Single entry for plugin packaging CI.

### Who invokes

| Actor | When |
|---|---|
| operator | Pre-publish Foundry plugin |
| eval | CI registry integrity job |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--root` | no | Registry bundle root (default: `.cursor/foundry`) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry registry validate --root registry:.cursor/foundry --json
```

### Sample JSON / exit code

Exit `0` when bundle is consistent. Exit `1` on broken references or schema errors.

```json
{
  "valid": true,
  "root": "registry:.cursor/foundry",
  "flow_valid": true,
  "schema_count": 12,
  "unresolved_paths": []
}
```

### Used by factory-flow checks / nodes

| Node / check | Role |
|---|---|
| — | Authoring/CI only |

### Cross-links

- [flow validate](#flow-validate) — included in bundle validation
- [capabilities.md](../workflow-schema-v1/capabilities.md) — `registry:` path grammar

---

## cli resolve

### Purpose

Resolve registered CLI capability ids (e.g. `app.validate`, `transition`, `artifact.publish`) to concrete `foundry` argv and document whether the active steward may invoke them. Used at engine startup and in eval harness capability audits.

### Who invokes

| Actor | When |
|---|---|
| engine | Before honoring steward CLI requests |
| operator | Debug capability allow lists |
| eval | Verify node `allow.cli` entries resolve |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--capability` | yes | Capability id (dot notation) |
| `--node` | no | Node id for allow-list check |
| `--flow` | no | Flow registry path |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry cli resolve --capability app.validate --node shape.intake --json
```

### Sample JSON / exit code

Exit `0` when capability resolves. Exit `1` when unknown or not allowed for node.

```json
{
  "capability": "app.validate",
  "argv": ["foundry", "app", "validate", "--workspace", "{workspace}"],
  "allowed_for_node": true,
  "node_id": "shape.intake",
  "read_only": true
}
```

### Used by factory-flow checks / nodes

| Node / check | Role |
|---|---|
| `allow.cli` on nodes | e.g. `shape.intake`: `artifact.publish`, `transition` |
| Command probes | Map catalog `command:` snake ids to argv templates |

### Cross-links

- [capabilities.md](../workflow-schema-v1/capabilities.md) — `allow.cli` defaults and rules
- [cli.md](cli.md) — hub command index
- [cli-check.md](cli-check.md) — probe dispatch from `check eval`

---

For CLI mechanics borrowed from earlier prototypes, see [cli-poc-transition.md](cli-poc-transition.md).
