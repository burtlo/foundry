# Worker capability contracts

One `contract.yaml` per worker role under `workers/{worker-id}/`. Steward step behavior lives in `nodes/{node-id}/instructions.md` or `judgment.md` plus registry tasks. Optional Cursor subagents for meta-work (spec sync, run review) live under `.cursor/agents/` (`scribe`, `scribe-verifier`, `run-evaluator`).

| Path | Role |
|------|------|
| `_protocol.yaml` | Shared `protocol_version` for the workers directory |
| `{worker-id}/contract.yaml` | Capabilities, write scopes, required receipt fields, and per-mode `valid_next_states` |

Legacy flow steps may still reference contracts for receipt field validation; the default host path does not bind worker prompts from `.cursor/agents/`.

```yaml
worker:
  contract: registry:workers/intake-checker.shape/contract.yaml
  mode: shape
```

- `contract` resolves under `.cursor/foundry/workers/{worker-id}/contract.yaml`.
- `mode` selects a block inside the contract file.

Legacy monolithic `registry.yaml` and the former `agents/` directory name are still supported by the PoC engine for path resolution (`registry:agents/...` → `.cursor/agents/...`).
