# Agent adapter configuration

Host configuration selects how judgment tasks reach a model provider. Workflow YAML declares **tasks**; adapters implement transport and authentication.

## Environment variables

| Variable | Values | Purpose |
| --- | --- | --- |
| `FOUNDRY_AGENT_ADAPTER` | `stub` \| `http` | Explicit adapter selection. When unset, the host does **not** default to stub in user/production mode. |
| `FOUNDRY_AGENT_HTTP_URL` | HTTPS or HTTP URL | Required when `FOUNDRY_AGENT_ADAPTER=http`. Endpoint that accepts agent invocations. |
| `FOUNDRY_ALLOW_STUB_ADAPTER` | `1`, `true`, `yes` | Opt-in for local development: allows implicit `stub` when `FOUNDRY_AGENT_ADAPTER` is unset. Pytest sets this via test harness; do not rely on it in production. |

Optional stub-only overrides (tests/local):

- `FOUNDRY_AGENT_STUB_RESULT` — JSON object replacing the task result for a stub invocation.

Production runs should set `FOUNDRY_AGENT_ADAPTER=http` and `FOUNDRY_AGENT_HTTP_URL`. Stub auto-selection and `FOUNDRY_VERIFY_ACCEPTANCE_DECISION` are confined to CI/test stub paths (`FOUNDRY_ALLOW_STUB_ADAPTER`, `FOUNDRY_EXECUTE_STUB`); they are not production verify controls.

## In-repo judgment bridge

Foundry ships **`foundry bridge start`**, an HTTP server that implements the contract below using the Cursor SDK. Set `FOUNDRY_CURSOR_API_KEY` on the bridge process; point the job host at the bridge URL before `foundry host start`. See [judgment-bridge.md](../features/judgment-bridge.md), [bridge start](../cli/bridge-start.md), and the [operator runbook](../operator-runbook.md).

## HTTP adapter contract

The HTTP adapter (`HttpAgentAdapter`) POSTs an immutable agent request built by `build_agent_request` (see [job-host-architecture.md](job-host-architecture.md) — Agent connection contract).

**Request**

- Method: `POST`
- Header: `Content-Type: application/json`
- Body:

```json
{
  "request": {
    "protocol_version": 1,
    "request_id": "ar_...",
    "run_id": "...",
    "visit_id": "...",
    "task_id": "shape.examine",
    "attempt": 1,
    "definition_digest": "sha256:...",
    "input_digest": "sha256:...",
    "instructions": "...",
    "input": {},
    "output_schema": "registry:schemas/...",
    "limits": {"max_input_chars": 24000, "timeout_seconds": 120},
    "capabilities": {"tools": [], "file_writes": false}
  }
}
```

Timeout: `limits.timeout_seconds` from the request, default **120** seconds.

**Response**

JSON object. The host requires a **`result`** object (task semantic output); it must validate against the task output schema after dispatch. Optional envelope fields:

```json
{
  "provider_request_id": "provider-specific-id",
  "raw_response_ref": "run:artifacts/...",
  "usage": {"input_tokens": 0, "output_tokens": 0},
  "finish_reason": "stop",
  "result": {}
}
```

`request_id` and `attempt` in the returned `AgentAdapterEnvelope` are taken from the immutable request, not from the HTTP body. Missing `result` or transport errors surface as `RuntimeError` from the adapter.

## Stub adapter

`StubAgentAdapter` returns deterministic results per `task_id` for CI and local runs. It does not call the network. Use only with `FOUNDRY_AGENT_ADAPTER=stub` or when stub is allowed via `FOUNDRY_ALLOW_STUB_ADAPTER` / pytest.

## `get_adapter()`

- Unset `FOUNDRY_AGENT_ADAPTER` + stub not allowed → `RuntimeError` (configure http or explicit stub).
- `FOUNDRY_AGENT_ADAPTER=stub` → `StubAgentAdapter`.
- `FOUNDRY_AGENT_ADAPTER=http` → `HttpAgentAdapter` (requires `FOUNDRY_AGENT_HTTP_URL`).
- Unknown value → `ValueError`.

Inject adapters in tests via `advance_run(..., agent_adapter=...)` or host handler construction; production host paths call `get_adapter()` when no override is passed.
