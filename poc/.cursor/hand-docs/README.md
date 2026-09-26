# Hand-authored documentation archive (disconnected)

Historical design and authoring documents preserved under `poc/` for reference only. **Nothing in the active product tree links here.**

## Hand-authored (archived here)

| Path | Former `docs/` location | Role |
|---|---|---|
| [transitions/](transitions/) | `docs/transitions/` | POC→v1 port notes, steward authoring, intake-checker history |
| [cli-v1/](cli-v1/) | `docs/cli-v1/` | Draft CLI capability specs (markdown only) |
| [workflow-schema-v1/](workflow-schema-v1/) | `docs/workflow-schema-v1/` | Workflow schema v1 design definition |
| [nodes/](nodes/) | `docs/nodes/` | Hand node references (e.g. shape.intake) |

## Not archived (still active)

| Path | Role |
|---|---|
| [docs/](../../../docs/) | **Tool-generated** node/worker docs (`foundry dev docs`) |
| [docs/v1-spec.md](../../../docs/v1-spec.md) | Locked product spec |
| [.cursor/foundry/cli/tests/acceptance/features/](../../../.cursor/foundry/cli/tests/acceptance/features/) | Gherkin acceptance contracts (executable tests) |

## Tool-generated vs hand-authored

- **Hand-authored:** transitions, cli-v1 markdown, workflow-schema-v1, archived nodes — written and maintained by authors.
- **Tool-generated:** `docs/` (nodes, catalog, index) — produced by `foundry dev docs` from `factory-flow.yaml`, schemas, and `nodes/*/doc.yaml` annotations.
