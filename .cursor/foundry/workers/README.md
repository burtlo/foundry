# Worker capability contracts

One `contract.yaml` per worker role under `workers/{worker-id}/`, parallel to `.cursor/agents/{worker-id}.md` (subagent prompts) and `nodes/{node-id}/instructions.md` (steward instructions).

| Path | Role |
|------|------|
| `_protocol.yaml` | Shared `protocol_version` for the workers directory |
| `{worker-id}/contract.yaml` | Capabilities, write scopes, required receipt fields, and per-mode `valid_next_states` |

Flow steps bind workers explicitly:

```yaml
worker:
  prompt: registry:agents/intake-checker.shape.md
  contract: registry:workers/intake-checker.shape/contract.yaml
  mode: shape
```

- `prompt` resolves under `.cursor/` (typically `.cursor/agents/`).
- `contract` resolves under `.cursor/foundry/workers/{worker-id}/contract.yaml`.
- `mode` selects a block inside the contract file.

Legacy monolithic `registry.yaml` and the former `agents/` directory name are still supported by the PoC engine.
