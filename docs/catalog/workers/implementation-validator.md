# Worker: `implementation-validator`

**Prompt:** [registry:agents/implementation-validator.md](../../../.cursor/agents/implementation-validator.md)

**Contract:** [registry:workers/implementation-validator/contract.yaml](../../../.cursor/foundry/workers/implementation-validator/contract.yaml)

## Capabilities

- `validation`

## Required output fields

- `outputs.summary_markdown`
- `outputs.findings`

## Modes

### `validate`
- **valid_next_states:** `verify.code_quality`, `execute.plan`, `shape.intake`, `execute.intake`

## Used by nodes

- [verify.acceptance](../../nodes/verify.acceptance.md)
