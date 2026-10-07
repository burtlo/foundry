# Flow-derived node capability cleanup

Status: **done** (2026-10-07)  
**As-built:** [implementation-flow-runtime.md](../../features/implementation-flow-runtime.md)

## Delivered

- `execute_verify_deliver_flow_node_ids()` derived from implementation flow registry order.
- Removed `EXECUTE_VERIFY_DELIVER_NODE_IDS`, `audit_rows`, and judgment frozensets from `node_capability.py`.
- Tests use flow-derived IDs; dropped duplicate classifier/audit label inventories.
- Removed `GIT_MECHANICAL_STEP_NODE_IDS`; git-mechanical coverage from `runtime.advance`.
- `task_registry_contract_errors` validates `complete_action` is registered; registry_refs unit tests.
- Removed unused `CAP_VISIT_VERIFY_ACCEPTANCE_COMPLETE`.

## Verification

| Check | Result |
|-------|--------|
| `just unit` | PASS (at delivery) |
| `just validate-app` | PASS (at delivery) |
