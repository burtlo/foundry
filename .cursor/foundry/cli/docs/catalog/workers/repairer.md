# Worker: `repairer`

**Prompt:** [registry:agents/repairer.md](../../../../../agents/repairer.md)

**Contract:** [registry:workers/repairer/contract.yaml](../../../../workers/repairer/contract.yaml)

## Capabilities

- `work_item`
- `repair`

## Required output fields

- `outputs.summary_markdown`
- `outputs.files_changed`
- `commands`

## Modes

### `repair`
- **valid_next_states:** `execute.commit`, `execute.build`

## Used by nodes

- [execute.test](../../nodes/execute.test.md)
