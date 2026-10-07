# Host auto-advance daemon

**Doc kind:** feature-record

## Summary

When enabled, the job host runs `AutoAdvanceLoop`: a background thread that periodically calls `advance_run_durable` for each non-terminal run in `.foundry/runs/` that does not require human input.

## Enable

```bash
foundry host start --auto-advance
foundry host run --auto-advance   # foreground / tests
```

Optional: `--auto-advance-interval` (default `2` seconds). Detached host receives flags via `python -m foundry_cli.host --auto-advance`.

## Observability

| Artifact | Path |
|----------|------|
| Host log | `.foundry/host/host.log` |
| Startup / bind errors | `.foundry/host/startup.log` |
| Auto-advance telemetry | `.foundry/host/auto_advance.json` |

```bash
foundry host status          # running, auto-advance flags, last tick summary
foundry host logs            # tail host.log (default 200 lines)
foundry host logs -f         # follow host.log
foundry host logs --source startup
foundry host logs --json     # structured tail for scripts
```

Set `FOUNDRY_HOST_LOG_LEVEL=DEBUG` on the host process for per-run skip lines.

## Policy

| `wait.kind` | Auto-advance |
|-------------|----------------|
| *(none)* | Yes |
| `agent` | Yes (uses host `get_adapter()` / env) |
| `decision` | No — use `foundry decide` |
| `user_input` | No — use `foundry answer` |
| `operator` | No — fix workspace, then `run advance` |

Skipped when `status` is terminal or `paused`.

On ticks with no successful advances, scan interval backs off up to 30s.

## Code map

| Module | Role |
|--------|------|
| `foundry_cli/host/auto_advance.py` | `AutoAdvanceLoop`, `should_auto_advance_snapshot` |
| `foundry_cli/host/server.py` | Starts/stops loop with host |

## Tests

`tests/unit/test_auto_advance.py`
