# Execute build (host-owned)

## Scope

`execute.build` is an **engine-owned** step. The host runs **`commands.build`** from the app manifest (`.foundry/app.yaml`), records command exit codes in a sealed `feature-builder` agent receipt, patches `last_build_exit_code`, and routes to `execute.test`.

This step **does not** wait for builder agents, prove execution-graph work items against the workspace, or require a product diff. **Shaped-work satisfaction** is enforced later at **verify** acceptance (policy G3 / workflow §14).

## Test-only stubs

Set **`FOUNDRY_EXECUTE_STUB=1`** (and optionally **`FOUNDRY_EXECUTE_BUILD_EXIT_CODE`**) only in **tests or CI**. Stub commands are not the product contract for implementation proof.

## Steward actions

1. Ensure the run is on the feature branch with plan state present (`execution_graph_id`, `feature_branch`).
2. Call **`run advance`** when the host is not auto-advancing.
3. The **first** advance after admission from **`execute.plan`** or **repair re-entry** may **park once** with reason **`execute_build_boundary`** or **`repair_reentry_boundary`**. This is a one-step host boundary—not an agent work window.
4. Call **`run advance`** again to run build commands and seal the visit.

Do not bind task-registry builder workers on the default host slice. Do not treat a passing stub build as proof that AC-shaped work landed in the repo.
