# `run context`

Status: **implemented**

Assemble the steward context packet for a visit: reads, allow grants, artifact declarations, worker binding, and instructions path. Use `--json` for the context-packet envelope or `--markdown` for a single steward document with inlined step instructions.

## Invocation

```bash
foundry run context [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--visit` | no | — | Visit id (default: active visit) |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--flow` | no | — | Flow id override |
| `--markdown` | no | false | Emit steward context as a single markdown packet (mutually exclusive with --json) |
| `--local` | no | false | Assemble context from disk when the job host is running |


## Output modes

| Mode | Flag | Audience | Contents |
|---|---|---|---|
| JSON | `--json` | Programs, schema validation | `context-packet.schema.json` envelope; includes `instructions_path` but not inlined instruction text |
| Markdown | `--markdown` | Phase stewards | Single document with metadata sections and step instructions inlined verbatim |

`--json` and `--markdown` are mutually exclusive. Stewards SHOULD use `--markdown` and follow one document. Step files under `.cursor/foundry/nodes/` remain the authoring source; the CLI is a renderer.

See [capabilities.md](../../concepts/capabilities.md#steward-context) for steward-context semantics.


## Sample invocations

```bash
foundry run context --run-dir .cursor/foundry/fixtures/runs/porcelain-0007-v001 --markdown
foundry run context --run-dir .cursor/foundry/fixtures/runs/porcelain-0007-v001 --json
```


## Sample markdown output (abbreviated)

```markdown
# Steward context — shape.intake (v-001)

_Shape intake — publish ticket and seal receipts_

## Position

- run_id: `porcelain-0007`
- visit_id: `v-001`
- node_id: `shape.intake`
- kind: `step`
- lifecycle: `opened`

## Reads

### Config
| Key | Value |
|---|---|
| workspace | . |

## Allow

### CLI
- `visit.intake.complete`
- `visit.state_patch`

## Produces

### Artifacts
| ID | URI | Resolved URI |
|---|---|---|
| ticket | `run:artifacts/{visit_id}/ticket.json` | `run:artifacts/v-001/ticket.json` |

---

## Intake

Engine-owned step: use `visit intake complete` (or `run advance` when `config.shape.work_prompt` is set). Step instructions resume at `shape.examine`.
```

## Schema

[registry:schemas/context-packet.schema.json](../../.cursor/foundry/schemas/context-packet.schema.json)

## Acceptance

[run_context.feature](../../.cursor/foundry/cli/tests/acceptance/features/run_context.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
