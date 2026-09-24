# Worker capability contracts

One YAML file per worker role, parallel to `steps/*.md` (step instructions) and `.cursor/agents/*.md` (subagent prompts).

| File | Role |
|------|------|
| `_protocol.yaml` | Shared `protocol_version` for the directory |
| `{worker}.yaml` | Capabilities, write scopes, required receipt fields, and per-mode `valid_next_states` |

Flow steps bind workers explicitly:

```yaml
worker:
  prompt: agents/intake-checker.md
  contract: contracts/intake-checker.yaml
  mode: shape
```

- `prompt` resolves under `.cursor/` (typically `.cursor/agents/`).
- `contract` resolves under `.cursor/foundry/contracts/`.
- `mode` selects a block inside the contract file.

Legacy monolithic `registry.yaml` and the former `agents/` directory name are still supported by the PoC engine.
