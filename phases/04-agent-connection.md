# Phase 4 — Model API connection

Status: **complete**

Related: [job-host architecture](../docs/concepts/job-host-architecture.md), [Phase 3](03-job-host.md), [delivery index](README.md).

## Design

### Task binding

- Registry task `shape.examine` in `.cursor/foundry/tasks/shape.examine.yaml` binds judgment prompt (`judgment.md`), bounded input selection, and strict output schema `shape-examination-result.schema.json`.
- Host configuration selects the adapter implementation (`FOUNDRY_AGENT_ADAPTER=stub` default in CI).

### Agent request (immutable)

- On `wait.kind=agent` at `shape.examine`, the engine persists an immutable **agent request** on the snapshot (`agent_requests[request_id]`) and appends ledger event **`agent.requested`**.
- `run.wait.request_ref` is the `request_id` (`ar_…`).
- Requests record `definition_digest`, `input_digest`, `instructions`, `input`, `output_schema`, and `limits`.

### Adapter

- **`AgentAdapter`** interface: `invoke(request) -> AgentAdapterEnvelope`.
- **`StubAgentAdapter`** (default): returns configurable JSON from `FOUNDRY_AGENT_STUB_RESULT` or a valid zero-question examination result — no API key in CI.
- Optional **`HttpAgentAdapter`** hook when `FOUNDRY_AGENT_ADAPTER=http` (env-gated; not used in unit tests).

### Submit path

- **`run agent submit`** and host method **`run.agent.submit`** validate `result` against the task schema, accept idempotently, append **`agent.result.accepted`**, patch examination state from the structured result, clear or replace `run.wait`, bump revision under lock.
- Duplicate submit with the same `request_id` returns success without double-applying state.

### Advance integration

- After durable advance, the host dispatches the adapter for pending agent requests (stub in tests).
- `_boundary_wait_for_visit` at `shape.examine`: agent wait until a result is accepted; then **`user_input`** when structured questions remain; otherwise advancement may continue toward steward seal/transition (unchanged Phase 1 path).

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| Task definition + output schema for `shape.examine` | Met |
| Immutable agent request + `agent.requested` | Met |
| `wait.kind=agent` with `request_ref` | Met |
| Adapter interface + stub (CI-safe) | Met |
| `run.agent.submit` / `run agent submit` with validation + idempotency | Met |
| Host dispatches adapter on agent wait | Met |
| Engine patches examination fields; routing uses derived question count | Met |
| Unit validation + integration advance→wait→submit→advance | Met |

## Verification

From `.cursor/foundry/cli`:

```text
python -m pytest tests/unit/test_agent_connection.py tests/unit/test_advance.py tests/unit/test_host_protocol.py -q
```

## Out of scope (later phases)

- User `foundry shape` / attach UX (Phase 5)
- Execute/verify (Phase 6)
- General agent tool platform
