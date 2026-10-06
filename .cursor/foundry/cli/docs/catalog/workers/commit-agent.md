# Worker: `commit-agent`

**Prompt:** [registry:agents/commit-agent.md](../../../../../agents/commit-agent.md)

**Contract:** [registry:workers/commit-agent/contract.yaml](../../../../workers/commit-agent/contract.yaml)

## Capabilities

- `git_commit`

## Required output fields

- `outputs.summary_markdown`
- `outputs.final_commit_sha`
- `outputs.execute_commit_message`

## Modes

### `execute`
- **valid_next_states:** `verify.intake`

## Used by nodes

- [execute.commit](../../nodes/execute.commit.md)
