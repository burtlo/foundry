# artifact

Status: **draft capability spec**

The `foundry artifact` command group publishes declared node outputs into the immutable artifact store. Publication maps to `publish_artifact` in [artifacts.md](../workflow-schema-v1/artifacts.md): validate against declaration, materialize or normalize reference, compute digest, append `artifact.linked`, and return the concrete reference.

---

## publish

### Purpose

Publish one declared artifact for the active visit. Required before `visit transition` when `on_seal` completeness validation runs on `produces.artifacts`.

### Who invokes

| Actor | When |
|---|---|
| steward | Step completes declared output (ticket, plan, presentation, branch diff, etc.) |
| engine | May proxy on behalf of worker tools when capability granted |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--visit` | no | Visit id (default: active visit) |
| `--artifact` | yes | Logical artifact id from node `produces.artifacts` |
| `--source` | yes* | Source path or reference value (*kind-dependent) |
| `--media-type` | no | Override declared media type |
| `--json` | no | Emit machine-readable result |

### Sample invocation (document)

```text
foundry artifact publish --run run-2026-09-24-porcelain-003 --artifact ticket --source workspace:.foundry/tmp/ticket.json --json
```

### Sample JSON result (document)

```json
{
  "artifact": {
    "id": "ticket",
    "kind": "document",
    "producer_node_id": "shape.intake",
    "producer_visit_id": "v-001",
    "uri": "run:artifacts/v-001/ticket.json",
    "schema": "registry:schemas/ticket.schema.json",
    "media_type": "application/json",
    "digest": "sha256:8f3a2b1c..."
  },
  "ledger_seq": 12
}
```

### Sample invocation (reference — `git_commit`)

```text
foundry artifact publish --run run-2026-09-24-porcelain-003 --visit v-015 --artifact final-commit --source git:commit/4f91c2a --json
```

### Sample JSON result (reference)

```json
{
  "artifact": {
    "id": "final-commit",
    "kind": "reference",
    "scheme": "git_commit",
    "producer_node_id": "execute.commit",
    "producer_visit_id": "v-015",
    "uri": "git:commit/4f91c2a",
    "digest": "sha256:c4e9..."
  },
  "ledger_seq": 58
}
```

Reference artifacts record an immutable external identifier; they do not copy repository content into the artifact store per [artifacts.md](../workflow-schema-v1/artifacts.md).

### Ledger events appended

| Event | Payload highlights |
|---|---|
| `artifact.linked` | `artifact id`, `producer visit id`, `uri`, `schema`, `media_type`, `digest` |

Must precede the close request that depends on completeness per [run-record.md](../workflow-schema-v1/run-record.md).

### Related factory-flow.yaml nodes/checks

| Node | Artifact id | Kind |
|---|---|---|
| `shape.intake` | `ticket` | document |
| `shape.present` | `presentation` | document |
| `shape.record` | `plan` | document |
| `execute.commit` | `final-commit` | reference (`git_commit`) |
| `verify.intake` | `branch-diff` | document |
| `verify.acceptance` | `verify-findings` | document |
| `verify.code_quality` | `code-quality-report` | document (`allow.cli` includes `artifact.publish`) |
| `verify.code_review` | `verify-notes` | document |

Completeness enforced automatically before seal; `final-commit-recorded` check on `execute.commit` reads state derived from published `final-commit`.

### Cross-links

- [cli-visit.md](cli-visit.md) — `transition` after artifacts satisfy cardinality
- [cli-ledger.md](cli-ledger.md) — `artifact.linked` history
- [artifacts.md](../workflow-schema-v1/artifacts.md) — `reads.artifacts` consumption (`shape.intake.ticket`, etc.)
- [cli-run.md](cli-run.md) — `integrity-check` artifact suite
