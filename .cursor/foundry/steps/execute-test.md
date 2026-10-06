# execute.test

Host-owned verification step: run repo test commands and seal repairer-mode evidence for the test gate.

## Preconditions

- Prior sealed `execute.build` (`prior-execute-build-sealed` on examine).

## Host behavior

1. Select verification policy from app manifest:
   - `implementation` on the first pass.
   - `post_repair` after any `connection.taken` with `loop: repair`.
2. Run commands:
   - When `FOUNDRY_EXECUTE_STUB=1`, use `foundry-stub:test` (exit from `FOUNDRY_EXECUTE_TEST_EXIT_CODE`, default `0`).
   - Otherwise run each command named in the selected `verification` policy via `commands.*` in `.foundry/app.yaml`.
3. Seal `registry:schemas/agent-receipt.schema.json` (`repairer`, repair mode) including `commands[]`.
4. `transition` to `execute.test.gate` (engine maps receipt exit codes to `pass` | `repair`).

## Steward / operator

Use `run advance` on `execute.test`. Failed verification routes to `execute.repair.limit.gate` when the gate decision is `repair`.
