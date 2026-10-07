# Judgment bridge (in-repo)

**Doc kind:** feature-record  
**Program:** [operator-integration-program.md](../plans/operator-integration-program.md) Phase 2

## Summary

`foundry bridge start` runs an HTTP server in the application workspace that implements the same POST contract as [`HttpAgentAdapter`](../concepts/agent-adapter.md). The host calls this URL when `FOUNDRY_AGENT_ADAPTER=http` and `FOUNDRY_AGENT_HTTP_URL` point at the bridge. Judgment results are produced via the **Cursor SDK** (`cursor-sdk` package), validated against registry task schemas, and returned as JSON; the bridge does not write run state.

## Judgment tasks

| `task_id` | Result schema |
|-----------|----------------|
| `shape.examine` | `shape-examination-result.schema.json` |
| `shape.present` | `shape-presentation-result.schema.json` |
| `shape.record` | `shape-record-result.schema.json` |
| `execute.plan` | `execute-plan-result.schema.json` |
| `verify.acceptance` | `verify-acceptance-result.schema.json` |

## Environment

| Variable | Process | Role |
|----------|---------|------|
| `FOUNDRY_CURSOR_API_KEY` | Bridge | Primary Cursor API key |
| `CURSOR_API_KEY` | Bridge | Fallback key name |
| `FOUNDRY_CURSOR_MODEL` | Bridge | Optional model id (default `composer-2.5`) |
| `FOUNDRY_AGENT_ADAPTER=http` | Job host | Select HTTP adapter |
| `FOUNDRY_AGENT_HTTP_URL` | Job host | Bridge URL (default listen `http://127.0.0.1:8791/v1/agent`) |

## Operator flow

CLI reference: [bridge start](../cli/bridge-start.md).

```bash
export FOUNDRY_CURSOR_API_KEY=...
foundry bridge start --workspace .
# separate terminal / process:
export FOUNDRY_AGENT_ADAPTER=http
export FOUNDRY_AGENT_HTTP_URL=http://127.0.0.1:8791/v1/agent
foundry host start
foundry shape --input "..."
```

Bridge uses `--workspace` as the Cursor SDK **local** `cwd` for agent runs.

## HTTP contract

- **POST** `{FOUNDRY_AGENT_HTTP_URL}` with body `{"request": <immutable agent request>}`.
- **Response:** `result` object required; optional `provider_request_id`, `usage`, `finish_reason`.
- **GET** `/health` on the same host/port returns `{"ok": true}`.

## Code map

| Area | Module |
|------|--------|
| CLI | `foundry_cli/bridge_commands.py` |
| HTTP server | `foundry_cli/judgment_bridge/server.py` |
| Cursor SDK | `foundry_cli/judgment_bridge/cursor_provider.py` |
| Schema validation | `foundry_cli/judgment_bridge/validate.py` |

## Tests

- `tests/unit/test_judgment_bridge.py`
- `tests/unit/test_operator_integration_smoke.py` (bridge + host + shape path; mocked SDK by default)
