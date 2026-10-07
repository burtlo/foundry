# Operator onboarding ergonomics — porcelain retro

Status: **open** — review with an agent to prioritize UX and CLI/host/bridge improvements.

**Context:** First real onboarding of the **porcelain** application repo as a Foundry workspace (sibling layout: `~/src/porcelain` + `~/src/foundry`). No top-level `foundry init` yet; configuration was created via `config init`, `app discover`, and `app init`.

**Audience for follow-up:** agent session focused on operator ergonomics (CLI output, host/bridge lifecycle, env/config, docs/runbook).

---

## Initial steward guidance (what went wrong in chat)

Early onboarding help from the Cursor steward **did not match** what production judgment actually requires. The operator followed that guidance before the conversation corrected course.

| What the steward said first | What was missing or wrong |
|-----------------------------|---------------------------|
| Run `foundry host start` (and `host status`) after `config validate` / `app validate` | No mention of **`FOUNDRY_AGENT_ADAPTER`** / **`FOUNDRY_AGENT_HTTP_URL`** before starting the host |
| Prerequisites framed as validate + host | No instruction to run **`foundry bridge start`** first (or at all) in that initial “next steps” list |
| Implied `shape` could follow once the host was up | `shape` needs a running host **with adapter env set at host start**, plus a **running bridge** for real judgment |

So the operator reasonably ran **`host start` with no judgment-related environment variables** and **without starting the bridge**, then hit `HOST_ERROR: No agent adapter configured` on `shape` and only later learned the bridge → host (with exports) → shape ordering.

This is both a **steward/runbook sequencing** problem and a **product** problem (the stack should fail clearer or wire defaults). Capture for agent review: first-touch instructions must list bridge + host env **before** `host start`, or a single `operator up` command must subsume them.

---

## Intended setup (complete operator flow — after corrections)

### One-time: Foundry CLI

From the **foundry** registry repo:

```bash
cd ~/src/foundry
just setup    # venv under .cursor/foundry/cli/.venv
```

There is no global `foundry` on `PATH`; the entrypoint is `foundry.sh` (or venv `python foundry.py`).

### Application workspace (porcelain)

`.foundry/foundry.yaml` points at the bundle:

```yaml
schema_version: 1
registry: ../foundry/.cursor/foundry
```

`.foundry/app.yaml` — app id `porcelain`, `make build` / `make test` for verification.

From **porcelain** root:

```bash
../foundry/.cursor/foundry/cli/foundry.sh config validate
../foundry/.cursor/foundry/cli/foundry.sh app validate
```

Optional: symlink or shell alias so `foundry` invokes `foundry.sh`.

### Judgment stack (documented operator flow)

Three long-lived or ordered pieces:

1. **Bridge** (foreground HTTP server, uses `FOUNDRY_CURSOR_API_KEY`):
   ```bash
   export FOUNDRY_CURSOR_API_KEY=...
   foundry bridge start   # blocks; default http://127.0.0.1:8791/v1/agent
   ```
2. **Job host** (background; must inherit adapter env **at start**):
   ```bash
   export FOUNDRY_AGENT_ADAPTER=http
   export FOUNDRY_AGENT_HTTP_URL=http://127.0.0.1:8791/v1/agent
   foundry host start
   ```
3. **Workflow CLI**:
   ```bash
   foundry shape --input-file tooling-001.md
   ```

Adapter settings are **environment variables only** — not in `foundry.yaml` or `host.yaml`.

### Workaround: detached host import failure

`host start` spawns `python -m foundry_cli.host` with `cwd` = application workspace. `foundry_cli` is not installed into the venv as a package, so the child can fail with `ModuleNotFoundError: No module named 'foundry_cli'`.

Documented workaround until fixed in code:

```bash
export PYTHONPATH=/Users/lynnfrank/src/foundry/.cursor/foundry/cli
foundry host start
```

Acceptance tests spawn the host with `cwd` = CLI directory; production `host start` does not.

---

## What the operator did and observed

| Step | Action | Result |
|------|--------|--------|
| Steward | First “next steps” after `.foundry/` bootstrap | Said `host start` + `shape`; did **not** say start bridge first or set adapter env before `host start` |
| CLI | `just setup` in foundry | Succeeded; venv + deps including `cursor-sdk`, `textual` |
| Config | `config validate` / `app validate` without `--json` | Printed `error [None]: None` despite success |
| Host | `host start` per initial steward advice (no `FOUNDRY_AGENT_*`, bridge not running) | Host could show `running=True` but `shape` failed with no agent adapter |
| Config | Same commands with `--json` | `ok: true`, registry and manifest valid |
| Host | `host start` from porcelain (no `PYTHONPATH`) | `HOST_START_FAILED`: discovery state not published in time |
| Host logs | `host logs` | First line: `ModuleNotFoundError` (no timestamp); later line: `Host logging configured` with timestamp; trailing `error [None]: None` from CLI |
| Host | `host start` with `PYTHONPATH` set | Host eventually reported `running=True` (unix socket under `.foundry/host/`) |
| Adapter | Exported `FOUNDRY_AGENT_*` in shell used for `shape` only | `HOST_ERROR`: no agent adapter — host had been started **before** those exports |
| Adapter | Restart host in shell that already had `FOUNDRY_AGENT_*` + `PYTHONPATH` | Adapter configured in host process; `shape` reached bridge |
| Bridge | `bridge start` from **foundry** repo cwd | Log showed `workspace=/Users/lynnfrank/src/foundry` (wrong app tree for porcelain work) |
| Bridge | `bridge start` from porcelain | Correct workspace in log; process blocks (expected) |
| Shape | `shape --input-file tooling-001.md` | Host → bridge → Cursor SDK HTTP 200, then bridge **502** (see bug below) |
| Status | `host status --json` after failures | Sometimes `running: false` with stale `host.pid` / `started_at`; `health: null`; `host stop` clears dead PID state |
| Status | `host start --json` when PID exists but unhealthy | `already_running: true` with `running: false` possible (PID alive check ≠ socket health) |

---

## Bug encountered (shipped behavior gap)

**Symptom:** Bridge log:

```text
RuntimeError: Cursor agent run failed with status 'finished'
POST /v1/agent HTTP/1.1" 502
```

**Cause:** `cursor_provider.invoke_judgment` treats SDK `run_result.status` as failure unless it is one of `completed`, `succeeded`, `success`, `done`. Real `cursor-sdk` (1.0.36) returned **`finished`** for a successful run after `CreateAgent` / `Send` returned HTTP 200.

**Impact:** Judgment steps fail even when Cursor succeeds; host advance fails; operator sees bridge 502 and unclear host state.

**Fix direction:** Treat `finished` as success (and align allowlist with SDK docs); add unit test mirroring real status strings.

**File:** `.cursor/foundry/cli/foundry_cli/judgment_bridge/cursor_provider.py`

---

## Ergonomics pain points (for agent prioritization)

Use this list as the backlog seed for a dedicated ergonomics pass. Grouped by theme.

### Discovery and documentation

- **Steward first-touch guidance** told the operator to run `host start` without adapter environment variables and did not say to **start the bridge before the host** — matches operator confusion and wasted restart cycles.
- No single `foundry init` for app repos; bootstrap is split (`config init`, `app discover`, `app init`, manual commit of `.foundry/`).
- Operator must discover that CLI lives in **foundry** repo (`just setup`) while work happens in **another** project — mental overhead and path gymnastics (`../foundry/.cursor/foundry/cli/foundry.sh`).
- Bridge startup message tells operator to set env vars on the **host**, but those cannot live in `foundry.yaml` / `host.yaml` — easy to assume YAML config covers adapter wiring.

### CLI human output

- Many successful commands print **`error [None]: None`** when not using `--json` (e.g. `config validate`, `app validate`, `cli resolve`, `host logs`). Looks like failure; forces `--json` for sanity.
- Root cause pattern: success path with no entry in `FORMATTER_REGISTRY` falls through to `_format_error`.

### Host lifecycle and environment

- **Extra `PYTHONPATH`** required for detached `host start` from an app workspace (import path / spawn `cwd` bug).
- **`FOUNDRY_AGENT_ADAPTER` / `FOUNDRY_AGENT_HTTP_URL` must be set in the shell that starts the host**, not only in the shell that runs `shape` — non-obvious; restarting host is required after exporting.
- Order and terminal count: bridge blocks in foreground; host is separate; ideal order (bridge first, then host with URL from bridge message) is easy to invert.
- Starting bridge **after** host does not reconfigure the host; operator may start host first, then bridge, then wonder why judgment still fails until host restart.
- `host start` when a stale or unhealthy PID exists: confusing `already_running` vs `running: false` in JSON.

### Host logs and observability

- `host logs` dumps raw file tail with **no header** (path, whether current host PID matches, time range).
- **First failure line** in `host.log` (stderr from failed spawn) has **no timestamp**; later structured logs do — hard to correlate.
- Log file accumulates **historical failures** (e.g. old `ModuleNotFoundError`) alongside current run — looks like active errors.

### Bridge UX

- **Must hold a dedicated terminal** for `bridge start`; no documented detached/daemon mode in operator flow.
- Bridge cannot be “attached” after host in a way that avoids host restart for adapter env (env is process-scoped).
- Bridge workspace must be **application** `--workspace`; starting from foundry repo silently uses wrong `cwd` for Cursor SDK.

### Performance and perceived hang

- **`host status` with bridge running** triggers a host RPC (`health`); operator perceived delay when bridge/host stack is up (worth profiling: socket timeout, health path, or blocking on bridge).

### Missing product seams (desired end state — not spec)

- One command or profile: `foundry operator up` (bridge + host, correct cwd, adapter URL wired, PYTHONPATH internal).
- Adapter defaults in `.foundry/host.yaml` or `foundry.yaml` (non-secret URL; secrets still env).
- `foundry` on PATH via install script or `pip install -e` from CLI package.
- Clear success lines for validate/logs commands; exit 0 + silence or `ok` line.

---

## Suggested agent review agenda

1. **P0 bugs:** host spawn `cwd` / `PYTHONPATH`; judgment bridge `finished` status; CLI `error [None]: None` on success.
2. **P1 operator path:** single doc or command sequence from empty app repo → `shape` works; **steward/runbook must not recommend `host start` without bridge + adapter env**; reduce terminal count (daemon bridge or compose).
3. **P1 config:** optional `host.yaml` (or similar) for `agent_adapter` + `http_url` applied when host starts.
4. **P2 observability:** `host logs` header, timestamp stderr redirects, stale-state clarity on `host status`.
5. **P2 performance:** why `host status` feels slow when bridge is up.

---

## References

- [operator-runbook.md](../operator-runbook.md)
- [agent-adapter.md](../concepts/agent-adapter.md)
- [judgment-bridge.md](../features/judgment-bridge.md)
- Skill: `.cursor/skills/foundry-app-bootstrap/SKILL.md`
- Host spawn: `.cursor/foundry/cli/foundry_cli/host_commands.py` (`_spawn_detached`, `cwd=ctx.workspace`)
- CLI formatters: `.cursor/foundry/cli/foundry.py` (`FORMATTER_REGISTRY`, `_format_result`)
