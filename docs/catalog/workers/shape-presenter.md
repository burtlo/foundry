# Worker: `shape-presenter`

**Prompt:** [registry:agents/shape-presenter.md](../../../.cursor/agents/shape-presenter.md)

**Contract:** [registry:workers/shape-presenter/contract.yaml](../../../.cursor/foundry/workers/shape-presenter/contract.yaml)

## Capabilities

- `presentation`
- `acceptance_criteria`

## Required output fields

- `outputs.summary_markdown`
- `outputs.presentation_artifact_path`

## Modes

### `shape`
- **valid_next_states:** `shape.record`, `shape.examine`

## Used by nodes

- [shape.present](../../nodes/shape.present.md)
