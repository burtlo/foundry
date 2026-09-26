# Worker: `intake-checker.shape`

**Prompt:** [registry:agents/intake-checker.shape.md](../../../.cursor/agents/intake-checker.shape.md)

**Contract:** [registry:workers/intake-checker.shape/contract.yaml](../../../.cursor/foundry/workers/intake-checker.shape/contract.yaml)

## Capabilities

- `intake`
- `manifest_validation`

## Required output fields

- `outputs.assessment_path`
- `outputs.summary_markdown`

## Modes

### `shape`
- **valid_next_states:** `shape.examine`

## Used by nodes

- [shape.intake](../../nodes/shape.intake.md)
