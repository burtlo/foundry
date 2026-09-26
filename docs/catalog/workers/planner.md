# Worker: `planner`

**Prompt:** [registry:agents/planner.md](../../../.cursor/agents/planner.md)

**Contract:** [registry:workers/planner/contract.yaml](../../../.cursor/foundry/workers/planner/contract.yaml)

## Capabilities

- `planning`
- `execution_graph`

## Required output fields

- `outputs.summary_markdown`
- `outputs.artifacts`

## Modes

### `plan`
- **valid_next_states:** `execute.build`

## Used by nodes

- [execute.plan](../../nodes/execute.plan.md)
