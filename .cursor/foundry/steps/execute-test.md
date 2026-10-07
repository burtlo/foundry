# Execute test (host-owned)

## Scope

`execute.test` is an **engine-owned** step. The host runs **verification commands** from the app manifest (`verification.implementation` or `verification.post_repair` after a repair loop), records exit codes in a sealed `repairer`-labeled agent receipt (`agent.mode: repair`), patches `last_test_exit_code` and `repair_loop_count`, and routes to **`execute.test.gate`**.

Pass vs repair routing happens at the gate, not by binding the repairer worker on the default host slice. This step **does not** enforce acceptance criteria against the diff; **verify** does.

## Test-only stubs

Set **`FOUNDRY_EXECUTE_STUB=1`** (and optionally **`FOUNDRY_EXECUTE_TEST_EXIT_CODE`**) only in **tests or CI**.

## Steward actions

1. After a sealed **`execute.build`**, call **`run advance`** when the host is not auto-advancing.
2. Read gate evidence at **`execute.test.gate`**; do not submit repairer task judgments on the default path.
