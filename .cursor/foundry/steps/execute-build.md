# execute.build

Host-owned build step: record builder command evidence and seal an agent receipt.

## Preconditions

- `execution_graph_id` and `feature_branch` set (`execution-graph-set`, `feature-branch-set` on examine).

## Host behavior

1. Run build commands:
   - When `FOUNDRY_EXECUTE_STUB=1`, use deterministic stub `foundry-stub:build` (exit code from `FOUNDRY_EXECUTE_BUILD_EXIT_CODE`, default `0`).
   - Otherwise run `commands.build` from `.foundry/app.yaml` when declared; else stub with exit `0`.
2. Seal `registry:schemas/agent-receipt.schema.json` (`feature-builder`, engine mode) with `commands[]` exit codes.
3. `on_seal` runs `validate-build-exit` and `agent-receipt-sealed` (non-zero exits reopen the visit).
4. `transition` to `execute.test`.

## Steward / operator

Use `run advance` on `execute.build`. Task-registry builder paths are out of scope for the default host slice.
