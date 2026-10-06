# Worker: `shape-recorder`

**Prompt:** [registry:agents/shape-recorder.md](../../../.cursor/agents/shape-recorder.md)

**Contract:** [registry:workers/shape-recorder/contract.yaml](../../../.cursor/foundry/workers/shape-recorder/contract.yaml)

## Capabilities

- `plan_freeze`
- `acceptance_criteria`

## Required output fields

- `outputs.assessment_path`
- `outputs.summary_markdown`
- `outputs.approved_ac_digest`
- `outputs.plan_path`

## Modes

### `shape`
- **valid_next_states:** `execute.intake`

## Used by nodes

- [shape.record](../../nodes/shape.record.md)
