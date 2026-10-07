# `bridge start`

Status: **implemented**

Start the in-repo HTTP judgment bridge (Cursor SDK; FOUNDRY_CURSOR_API_KEY) for FOUNDRY_AGENT_HTTP_URL.

## Invocation

```bash
foundry bridge start [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--host` | no | 127.0.0.1 | Listen address |
| `--port` | no | 8791 | Listen port |
| `--path` | no | /v1/agent | URL path for agent POST (default: /v1/agent) |
| `--log-level` | no | INFO | Logging level for the bridge process |

## Acceptance

[test_judgment_bridge.py](../../.cursor/foundry/cli/tests/unit/test_judgment_bridge.py)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
