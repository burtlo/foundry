# Foreground `foundry up` teardown probe (AC 13, win32)

Manual check that **Ctrl+C** in foreground mode stops children started by that invocation (bridge PID tracked when reconcile reported `started`, host when `cmd_host_start` returned a PID).

## Prerequisites

- Application workspace with valid `.foundry` manifest and `FOUNDRY_CURSOR_API_KEY` set (or Cursor auth available to the bridge).
- No other process bound to the default judgment bridge listen port (`127.0.0.1:8791`) for this workspace.
- PowerShell 5+ or Windows Terminal.

## Steps

1. From the app workspace root, start foreground up (human-readable stderr banner expected):

   ```powershell
   foundry up --foreground
   ```

2. Wait until JSON readiness shows `ready: true` (or the CLI prints a steady “up” state). Note bridge and host PIDs from `foundry host status` / bridge state if helpful.

3. Press **Ctrl+C** once in the same terminal.

4. Verify teardown:

   - `foundry host status` reports host not running (or PID gone).
   - Bridge state under `.foundry/bridge/state.json` is absent or PID is not alive.
   - Optional: `Get-Process -Id <bridge-pid>` / `Get-Process -Id <host-pid>` fail with “Cannot find a process”.

5. Run `foundry up` again (non-foreground) and confirm a clean reconcile (bridge spawn or already_running, host starts, `ready: true`).

## Pass criteria

- Ctrl+C returns promptly with foreground shutdown messaging.
- Host and bridge started by that foreground invocation are stopped; no orphaned `foundry_cli.judgment_bridge` or `foundry_cli.host` children remain for this workspace.

## Notes

- Automated coverage: `tests/unit/test_foundry_up_reconcile_hardening.py::test_cmd_up_foreground_stops_tracked_bridge_pid` (mocked reconcile spawn, KeyboardInterrupt on sleep).
- If the host was already running before foreground up, teardown only stops children recorded during that invocation (by design).
