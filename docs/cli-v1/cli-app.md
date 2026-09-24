# app

Status: **draft capability spec**

The `foundry app` command group discovers and validates the application repository manifest (`.foundry/app.yaml`). Manifest content drives `config.*` namespaces used by checks and stewards per [capabilities.md](../workflow-schema-v1/capabilities.md). Validation is a read-only probe suitable for catalog checks in [control-plane.md](../workflow-schema-v1/control-plane.md). Product bindings: [`/craft-init`](../v1-spec.md#bootstrap-craft-init) and phase intake manifest gates in [`v1-spec.md`](../v1-spec.md#intake-model-all-phases). Hub: [cli.md](cli.md).

---

## discover

### Purpose

Inspect the workspace repository and emit a proposed manifest draft (builders, verification commands, git settings, review flags) without writing files. First step of `/craft-init`.

### Who invokes

| Actor | When |
|---|---|
| steward | `/craft-init` before manifest write |
| operator | Explore bootstrap options for an unfamiliar repo |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--workspace` | no | Application repo root (default: cwd) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry app discover --workspace workspace:. --json
```

### Sample JSON / exit code

Exit `0` on success.

```json
{
  "workspace": "workspace:.",
  "proposed_manifest": {
    "app_id": "porcelain",
    "builders": {"default_owner": "general-builder"},
    "verification": {"commands": [{"id": "unit", "argv": ["make", "test"]}]},
    "git": {"branch_pattern": "{developer}/{run_slug}"},
    "review": {"enabled": true}
  },
  "warnings": []
}
```

### Used by factory-flow checks / nodes

| Node / check | Role |
|---|---|
| — | Not referenced directly; precedes `app init` at bootstrap |

### Cross-links

- [cli-app.md](cli-app.md) — `init`, `validate`
- [cli-registry.md](cli-registry.md) — `schema validate` for manifest schema
- [v1-spec.md](../v1-spec.md) — bootstrap charter

---

## init

### Purpose

Write `.foundry/app.yaml` from a validated discovery result or explicit manifest file. Hard block on validation failure (no partial write unless `--dry-run`).

### Who invokes

| Actor | When |
|---|---|
| steward | `/craft-init` completion |
| operator | Repair or re-bootstrap manifest |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--workspace` | no | Application repo root (default: cwd) |
| `--manifest-file` | no | Use an existing manifest file instead of in-memory discovery output |
| `--dry-run` | no | Validate and print path only; do not write |
| `--force` | no | Overwrite existing `.foundry/app.yaml` |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry app init --workspace workspace:. --json
```

### Sample JSON / exit code

Exit `0` when manifest is written (or would be written with `--dry-run`). Exit `1` on validation failure.

```json
{
  "workspace": "workspace:.",
  "manifest_path": "workspace:.foundry/app.yaml",
  "written": true,
  "validated": true
}
```

### Used by factory-flow checks / nodes

| Node / check | Role |
|---|---|
| — | Bootstrap only; subsequent runs use `validate-manifest` at intake |

### Cross-links

- [cli-app.md](cli-app.md) — `discover`, `validate`
- [cli-check.md](cli-check.md) — `validate-manifest` probe delegates here

---

## validate

### Purpose

Validate `.foundry/app.yaml` against `app-manifest.schema.json` and semantic rules (builder routes, verification config, readable paths). Read-only; suitable as the `validate-manifest` catalog command probe.

### Who invokes

| Actor | When |
|---|---|
| engine | `on_open` hook via `validate-manifest` check |
| steward | Phase intake workers seal results in intake receipt |
| operator | Pre-flight before starting a run |
| eval | Harness manifest fixture checks |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--workspace` | no | Application repo root (default: cwd) |
| `--manifest` | no | Explicit manifest path (default: `workspace:.foundry/app.yaml`) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry app validate --workspace workspace:. --json
```

### Sample JSON / exit code

When invoked as a check probe: exit `0` = pass, `1` = fail, `2` = not_applicable (per [control-plane.md](../workflow-schema-v1/control-plane.md#check-catalog)).

```json
{
  "valid": true,
  "manifest_path": "workspace:.foundry/app.yaml",
  "app_id": "porcelain",
  "errors": []
}
```

Failure example (exit `1`):

```json
{
  "valid": false,
  "errors": [
    {"code": "VERIFICATION_COMMAND_EMPTY", "path": "verification.commands[0].argv", "message": "argv must be non-empty"}
  ]
}
```

### Used by factory-flow checks / nodes

| Node / check | Hook | Role |
|---|---|---|
| `validate-manifest` | catalog `command: validate_manifest` | Probe body for manifest validity |
| `shape.intake` | `on_open` → `validate-manifest` | Shape intake hard gate |
| `execute.intake` | `on_open` → `validate-manifest` | Execute intake hard gate |
| `verify.intake` | `on_open` → `validate-manifest` | Verify intake hard gate |

### Cross-links

- [cli-check.md](cli-check.md) — `check eval --check validate-manifest`
- [control-plane.md](../workflow-schema-v1/control-plane.md) — command probe exit code mapping
- [validation.md](../workflow-schema-v1/validation.md) — structural vs semantic validation

---

For CLI mechanics borrowed from earlier prototypes, see [cli-poc-transition.md](cli-poc-transition.md).
