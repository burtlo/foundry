# Foundry Up — implementation map

Status: **ready for orchestration** — companion to [spec.md](spec.md) (approved 2026-10-13). Canonical map for implementer assignment, verifier checklists, and build order. Refreshed by merging prior drafts; use `/spec-implementation-map @spec.md` after material spec or code changes.

## Spec alignment

### Strengths (spec)

- **Clear operator outcome** and explicit **out-of-scope** boundaries (no `foundry ready`, no stale-PID reaper in v1, no steward UX) reduce scope creep.
- **Decision table (D1–D12)** ties each feature to retro evidence and acceptance criteria; **D3 as an order gate** (formatters before `up`) matches the lowest-risk trust fix.
- **Verification plan** names realistic scenarios (idempotency, wrong cwd, preflight, latency probe, foreground teardown) and points at existing test harnesses (`foundry.sh` stdout, integration smoke).
- **Readiness surface only on `up` exit (D4)** avoids duplicating `host status` while still requiring a richer status model for debugging (D5).

### Strengths (repository)

- **Workspace resolution** is centralized in `CommandContext.from_args` and already drives `bridge start`, `host start`, and `shape` from the invocation workspace (supports D1/D5 wrong-workspace reconcile once bridge state exists).
- **Host discovery and RPC** are mature: [host_commands.py](../../../.cursor/foundry/cli/foundry_cli/host_commands.py), [host/discovery.py](../../../.cursor/foundry/cli/foundry_cli/host/discovery.py), [host/client.py](../../../.cursor/foundry/cli/foundry_cli/host/client.py), and [host/server.py](../../../.cursor/foundry/cli/foundry_cli/host/server.py) provide detached start, health RPC, and stop (foundation for `up` reconcile).
- **Judgment bridge** HTTP contract and Cursor provider exist ([judgment_bridge/server.py](../../../.cursor/foundry/cli/foundry_cli/judgment_bridge/server.py), [cursor_provider.py](../../../.cursor/foundry/cli/foundry_cli/judgment_bridge/cursor_provider.py)); `finished` is already in successful SDK statuses (retro §4 partial fix).
- **Human formatters** exist for several command families ([foundry.py](../../../.cursor/foundry/cli/foundry.py) `FORMATTER_REGISTRY`); `host status` has a dedicated formatter (needs D5 reshape, not absent).
- **Operator integration smoke** ([operator_integration_smoke.py](../../../.cursor/foundry/cli/foundry_cli/operator_integration_smoke.py)) and acceptance/BDD harness can anchor first-run and formatter regression tests.
- **Host client timeouts** are explicit in [host/timeout_policy.py](../../../.cursor/foundry/cli/foundry_cli/host/timeout_policy.py) (baseline for D11 measurement; default health timeout is 30s and may dominate perceived latency).

### Gaps and clarifications before build

| Topic | Present state | Spec requirement | Suggested resolution |
|-------|---------------|------------------|----------------------|
| `foundry up` | No top-level `up` parser entry or handler ([parser.py](../../../.cursor/foundry/cli/foundry_cli/parser.py) stops at `bridge`, `host`, `shape`, …). | Single idempotent setup action with detach default and `--foreground` (D1, D2, D4, D10). | New `up_commands.py` (or `readiness/`) + parser/dispatch wiring; orchestrate bridge + host + env. |
| Bridge lifecycle | `bridge start` blocks in `serve_judgment_bridge` (foreground only); no workspace bridge discovery/state. | `up` starts/reconciles bridge for app workspace; wrong-cwd bridge must be fixed (AC 4–5). | Bridge discovery under `.foundry/` (parallel to host): pid, listen URL, workspace, `started_at`, optional `start_id`; health GET `/health`; reconcile on workspace/port/URL mismatch. |
| CLI success output | Unregistered successes fall through to `_format_error` → `error [None]: None` (verified in `test_foundry_entrypoint.py`). | D3 / AC 1: formatters for `config validate`, `app validate`, `cli resolve`, `host logs` before other bundle work. | Extend `FORMATTER_REGISTRY` + optional safe default; CLI integration tests on real `foundry.sh` stdout. |
| Host packaging | `cmd_host_start` spawns `sys.executable -m foundry_cli.host` with `cwd=app workspace` only; child does not inherit CLI `sys.path[0]` (retro §3). | AC 7 / D6: start works without caller `PYTHONPATH`. | Set `PYTHONPATH` to registry `cli` dir (from `cli resolve`) or equivalent; document in runbook. |
| Adapter at host start | `HostHandlers._agent_adapter` defaults `None`; advance uses `get_adapter()` when unset — reads **host process** env at advance time. | `up` configures host with bridge URL; AC 6: adapter ready in `up` summary without post-hoc export. | `up` sets `FOUNDRY_AGENT_ADAPTER=http` and `FOUNDRY_AGENT_HTTP_URL` in **spawn env** for host; persist in discovery for reconcile. |
| Adapter readiness definition | Host `health` RPC checks registry config validity, **not** `FOUNDRY_AGENT_*` or bridge reachability. | AC 2, 6, 8: separate adapter readiness in `up` and `host status`. | **Observed adapter** (env at host process) + optional **probe** (HTTP to bridge); document **configured** vs **reachable** in JSON field docs. |
| Status model | `host_status_payload` collapses to `running` (PID + health RPC); human formatter prints `host running=…` only. | D5 / AC 8: separate process, health, adapter; human three labeled lines. | Extend payload + `_format_host_status`; share helpers with `up` readiness where practical (see build order). |
| Status latency | Health path uses 30s default for `health` (inference: slow when host socket wedged). | D11 / AC 9: measured baselines + caps (3s / 5s / 8s provisional). | Probe script + recorded baselines; shorter status-only timeout; timed tests or documented probe. |
| Preflight | `shape` calls `_ensure_host` → auto `host start` without dependency report; no adapter check. `host start` has no preflight. | D7 / AC 10: missing bridge/host/adapter + next step (`foundry up`). | Shared `readiness/preflight.py` used by `host start`, `shape`, and internally by `up`. |
| Host logs | `cmd_host_logs` tails file; no header, no start marker, no `--since-start`. | D8, D12 / AC 11. | Marker on successful start/up; filter in `log_reader.py`; human header in formatter. |
| Judgment diagnostics | Bridge returns `502` + string `error`; HTTP adapter raises generic `RuntimeError`. | D9 / AC 12: layer + hint human; structured fields in `--json`. | Normalize errors in bridge, `http_adapter`, and advance/shape surfacing; contract tests on SDK/validation failures. |
| Foreground `up` | Not implemented. | D10 / AC 13: Ctrl+C stops children from this invocation + shutdown summary. | Track child PIDs in `up` session state; platform-specific process groups (`CREATE_NEW_PROCESS_GROUP` on win32). |
| `up` vs `shape` auto-start | `cmd_shape` auto-starts host when down but not bridge or adapter env on child. | D7: named next steps instead of silent partial fix. | Preflight **replaces or narrows** `_ensure_host` auto-start per spec. |
| GWT input path | [gwt-scenario.md](gwt-scenario.md) uses `plans/foundry-up.md`; AC3 uses `docs/plans/foundry-up.md` / [../foundry-up.md](../foundry-up.md). | One canonical first-run path in CI. | Align GWT, fixtures, and `shape --input-file` in first-run script (P4 verify). |
| Windows | Retro macOS-oriented; host uses Unix sockets off Windows; detached spawn differs (`CREATE_NO_WINDOW`). | Reliable first-run on operator platforms. | Idempotency, foreground Ctrl+C, latency probes on **win32** in verification matrix. |
| JSON schema for `up` | N/A. | Stable enough for future `foundry ready` (D4). | Draft in P4 PR: `workspace`, `bridge`, `host.process`, `host.health`, `adapter` (`ok`, `detail`, `recovery_hint?`). |
| Documentation | [operator-runbook.md](../../operator-runbook.md) documents manual `bridge start` + `host start` + env export. | `foundry up` as primary first-run path. | P10 runbook + docgen after `up` ships. |
| D11 baselines | Caps provisional; no probe note in bundle. | AC 9. | Land probe + baselines before locking CI thresholds (P6). |

### Acceptance criteria traceability

| AC | Present | Delta / work |
|----|---------|----------------|
| 1 | Partial — JSON ok; human falls through to error formatter for validate/resolve/logs families. | **P1** (D3 gate). |
| 2 | Missing — no `up` command or readiness payload. | **P4** (inline readiness dimensions; not blocked on P5). |
| 3 | Manual path only (bridge + host + env); GWT in [gwt-scenario.md](gwt-scenario.md). | **P4** + first-run integration test; **mocked bridge default CI**, live GWT optional/protected workflow. |
| 4 | Host idempotent skip when running; no bridge reconcile. | **P3**, **P4**. |
| 5 | Bridge workspace follows `CommandContext` but no reconcile if bridge already running elsewhere. | **P3**. |
| 6 | Adapter env not injected at host spawn. | **P4**. |
| 7 | Detached host spawn vulnerable to `ModuleNotFoundError` (retro-confirmed). | **P2**. |
| 8 | Single `running` flag semantics in JSON and human output. | **P5** (after P4 ships `up` summary). |
| 9 | No latency probe or caps in repo. | **P6**. |
| 10 | `shape` auto-starts host silently; no structured preflight. | **P7**. |
| 11 | Log tail only. | **P8**. |
| 12 | Opaque 502 / generic adapter errors. | **P9**. |
| 13 | No `up --foreground`. | **P4** (foreground slice). |

---

## Repository layout

Implementation lives in the **Foundry registry CLI bundle** under `.cursor/foundry/cli/`: entrypoint [foundry.sh](../../../.cursor/foundry/cli/foundry.sh) + [foundry.py](../../../.cursor/foundry/cli/foundry.py), package `foundry_cli/`, tests in `tests/unit` and `tests/acceptance`. Application workspaces hold `.foundry/` config and host metadata (`host/state.json`, logs). Plan bundle artifacts stay in `docs/plans/foundry-up/`. Operator docs: [operator-runbook.md](../../operator-runbook.md). Application repos resolve the bundle via `.foundry/foundry.yaml`; this repo is the registry source.

| Path | Role |
|------|------|
| [foundry.py](../../../.cursor/foundry/cli/foundry.py) | Dispatch, `FORMATTER_REGISTRY`, `_format_result` / `_format_error` |
| [foundry_cli/parser.py](../../../.cursor/foundry/cli/foundry_cli/parser.py) | CLI surface (add `up` subcommand) |
| [foundry_cli/commands.py](../../../.cursor/foundry/cli/foundry_cli/commands.py) | `cmd_config_validate`, `cmd_app_validate`, `cmd_cli_resolve` |
| [foundry_cli/bridge_commands.py](../../../.cursor/foundry/cli/foundry_cli/bridge_commands.py) | Bridge start (extend or delegate to lifecycle module) |
| [foundry_cli/host_commands.py](../../../.cursor/foundry/cli/foundry_cli/host_commands.py) | Host start/status/logs/stop |
| [foundry_cli/host/client.py](../../../.cursor/foundry/cli/foundry_cli/host/client.py) | `host_status_payload`, `call_host` |
| [foundry_cli/host/discovery.py](../../../.cursor/foundry/cli/foundry_cli/host/discovery.py) | Host state I/O (extend for start marker) |
| [foundry_cli/host/handlers.py](../../../.cursor/foundry/cli/foundry_cli/host/handlers.py) | Health RPC (optional adapter snapshot) |
| [foundry_cli/user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) | `cmd_shape`, `_ensure_host` |
| [foundry_cli/judgment_bridge/](../../../.cursor/foundry/cli/foundry_cli/judgment_bridge/) | Bridge server + `cursor_provider.py` |
| [foundry_cli/engine/agent/http_adapter.py](../../../.cursor/foundry/cli/foundry_cli/engine/agent/http_adapter.py) | Adapter HTTP client (diagnostics) |
| [foundry_cli/engine/agent/adapter.py](../../../.cursor/foundry/cli/foundry_cli/engine/agent/adapter.py) | `get_adapter()` rules |
| [foundry_cli/cli_docgen.py](../../../.cursor/foundry/cli/foundry_cli/cli_docgen.py) | Doc generation for `up` |
| [tests/unit/test_foundry_entrypoint.py](../../../.cursor/foundry/cli/tests/unit/test_foundry_entrypoint.py) | Formatter regression anchor |
| [tests/unit/test_judgment_bridge.py](../../../.cursor/foundry/cli/tests/unit/test_judgment_bridge.py) | Bridge error fixtures |
| [tests/acceptance/features/job_host.feature](../../../.cursor/foundry/cli/tests/acceptance/features/job_host.feature) | Host lifecycle acceptance |
| [operator_integration_smoke.py](../../../.cursor/foundry/cli/foundry_cli/operator_integration_smoke.py) | End-to-end operator script |

---

## Workstreams mapped to decisions

### D3 — CLI human success formatters (order gate)

**Present:** Success without registry formatter prints `error [None]: None` via `_format_error`.

**Required:** Information contract per family; no error-shaped success for listed commands; ship before `up`.

| Resource | Role |
|----------|------|
| [foundry.py](../../../.cursor/foundry/cli/foundry.py) | Register formatters; optional `_format_ok_default` fallback |
| [commands.py](../../../.cursor/foundry/cli/foundry_cli/commands.py) | Structured validate/resolve payloads |
| [host_commands.py](../../../.cursor/foundry/cli/foundry_cli/host_commands.py) | `cmd_host_logs` |
| [test_foundry_entrypoint.py](../../../.cursor/foundry/cli/tests/unit/test_foundry_entrypoint.py) | Extend beyond `run create` fallthrough |
| [tests/acceptance/helpers.py](../../../.cursor/foundry/cli/tests/acceptance/helpers.py) | Real CLI stdout regression |

**Risks:** Low. Broad default formatter may hide useful fields — keep family-specific lines minimal; preserve `_format_error` for failures.

### D6 — Host detached start packaging

**Present:** `_spawn_detached` uses same interpreter as CLI but module import depends on venv layout, not app cwd.

**Required:** `host start` / `up` succeed from clean sibling app workspace.

| Resource | Role |
|----------|------|
| [host_commands.py](../../../.cursor/foundry/cli/foundry_cli/host_commands.py) | Inject `env` with `PYTHONPATH` or invoke bundled wrapper |
| [foundry.sh](../../../.cursor/foundry/cli/foundry.sh) | Same python as CLI |
| [commands.py](../../../.cursor/foundry/cli/foundry_cli/commands.py) | `resolve_cli_path` helper |

**Risks:** Medium. Duplicating path logic vs `cli resolve` — prefer single helper shared with `up`.

### D1, D2, D4, D10 — `foundry up`

**Present:** Operators run `bridge start` and `host start` separately; no readiness summary type.

**Required:** Idempotent reconcile, default detach, structured readiness (human + JSON), foreground supervision and teardown.

| Resource | Role |
|----------|------|
| New `foundry_cli/up_commands.py` or `readiness/up.py` | Orchestration |
| New bridge discovery module | Bridge PID, port, workspace binding |
| [bridge_commands.py](../../../.cursor/foundry/cli/foundry_cli/bridge_commands.py) | Refactor detached bridge start |
| [parser.py](../../../.cursor/foundry/cli/foundry_cli/parser.py), [foundry.py](../../../.cursor/foundry/cli/foundry.py) | `foundry up`, `--foreground`, `--json` |
| [host_commands.py](../../../.cursor/foundry/cli/foundry_cli/host_commands.py) | Reuse start/stop; adapter env injection |
| [command_context.py](../../../.cursor/foundry/cli/foundry_cli/command_context.py) | Workspace reconcile |
| [operator_integration_smoke.py](../../../.cursor/foundry/cli/foundry_cli/operator_integration_smoke.py) | Bridge URL on host env pattern |

**Risks (high):** Bridge detached + discovery is new surface; **secrets** (`FOUNDRY_CURSOR_API_KEY`) must not log; **port conflicts** (default `8791`); **process ownership** for D10; **wrong-workspace bridge (AC5)**; define **healthy** for AC4 without restart churn.

### D5 — Host status model

**Present:** `host_status_payload` returns `running`, `host`, `health`; formatter emphasizes single `running`.

**Required:** Separate process / health / adapter; human three lines; JSON stable for future `ready`.

| Resource | Role |
|----------|------|
| [host/client.py](../../../.cursor/foundry/cli/foundry_cli/host/client.py) | Payload schema change |
| [foundry.py](../../../.cursor/foundry/cli/foundry.py) | `_format_host_status` |
| [job_host.feature](../../../.cursor/foundry/cli/tests/acceptance/features/job_host.feature) | Update assertions |

**Risks:** Breaking change for scripts reading `running` — deprecated alias or release note; refactor shared readiness helpers from P4 where possible.

### D7 — Preflight

**Present:** `_ensure_host` starts host on `shape` without reporting gaps.

**Required:** Checks before `host start` and `shape`; suggest `foundry up`.

| Resource | Role |
|----------|------|
| New `foundry_cli/readiness/preflight.py` | Shared checks |
| [user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py), [host_commands.py](../../../.cursor/foundry/cli/foundry_cli/host_commands.py) | Call preflight |

**Risks:** Medium. Behavior-breaking for implicit host start — document in runbook.

### D8, D12 — Logs and start marker

**Present:** `read_log_tail` / `cmd_host_logs` without metadata filter.

**Required:** Header; marker on successful start/up; `--since-start` or default scoped tail.

| Resource | Role |
|----------|------|
| [host/discovery.py](../../../.cursor/foundry/cli/foundry_cli/host/discovery.py) | `start_id`, `start_marker_at` |
| [host/log_reader.py](../../../.cursor/foundry/cli/foundry_cli/host/log_reader.py) | Filter by marker |
| [host_commands.py](../../../.cursor/foundry/cli/foundry_cli/host_commands.py) | Flags + header |
| [test_host_logs.py](../../../.cursor/foundry/cli/tests/unit/test_host_logs.py) | Extend tests |

### D9 — Judgment diagnostics

**Present:** Bridge `502` with string; adapter generic failures.

**Required:** Layer naming + recovery hint; JSON diagnostics.

| Resource | Role |
|----------|------|
| [judgment_bridge/server.py](../../../.cursor/foundry/cli/foundry_cli/judgment_bridge/server.py) | Structured error body |
| [cursor_provider.py](../../../.cursor/foundry/cli/foundry_cli/judgment_bridge/cursor_provider.py) | Typed validation vs transport |
| [http_adapter.py](../../../.cursor/foundry/cli/foundry_cli/engine/agent/http_adapter.py) | Map HTTP status / body |
| [test_judgment_bridge.py](../../../.cursor/foundry/cli/tests/unit/test_judgment_bridge.py) | Fixtures |

### D11 — Status latency

**Present:** No benchmarks in bundle; 30s health client timeout.

**Required:** Baseline probe note + CI or script + caps.

| Resource | Role |
|----------|------|
| New `docs/plans/foundry-up/probes/host-status-latency.md` or test module | Record baselines |
| [host/timeout_policy.py](../../../.cursor/foundry/cli/foundry_cli/host/timeout_policy.py) | Status-specific timeout |

### Documentation (spec §9)

| Resource | Change |
|----------|--------|
| [operator-runbook.md](../../operator-runbook.md) | First-run: `foundry up` primary |
| [docs/cli/](../../cli/) | `up` via docgen; host-status, host-logs |
| [docs/features/judgment-bridge.md](../../features/judgment-bridge.md) | Readiness / diagnostics cross-link |

---

## Orchestration packages

| ID | Title | Surfaces | Depends on | Primary paths | Verify (AC / tests) |
|----|-------|----------|------------|---------------|---------------------|
| P1 | Success formatters (D3 gate) | cli-ui, code | — | `foundry.py`, tests | AC 1; `test_foundry_entrypoint` + CLI stdout tests |
| P2 | Host spawn packaging (D6) | code, tooling | — | `host_commands.py` | AC 7; unit + sibling-app spawn test |
| P3 | Bridge discovery + detached lifecycle | code, config | P2 | new bridge discovery, `bridge_commands.py` | AC 4–5; wrong-cwd fixture |
| P4 | `foundry up` core + readiness JSON | cli-ui, code | P1, P2, P3 | `up_commands.py`, `parser.py`, `foundry.py` | AC 2, 4–6, 13; GWT / first-run script AC 3 |
| P5 | Host status model (D5) | cli-ui, code | P2, P4 | `host/client.py`, `foundry.py` | AC 8 |
| P6 | Status latency baselines + caps (D11) | ci, docs | P5 | probes, `timeout_policy.py` | AC 9 |
| P7 | Preflight (D7) | cli-ui, code | P3, P4 | `readiness/preflight.py`, `user_cli.py` | AC 10 |
| P8 | Log header + since-start (D8, D12) | cli-ui, code | P2, P4 | `log_reader.py`, `host_commands.py` | AC 11 |
| P9 | Judgment diagnostics (D9) | cli-ui, code | P3 | bridge, `http_adapter.py` | AC 12 |
| P10 | Operator runbook + docgen | docs | P4 | `operator-runbook.md`, `cli_docgen.py` | Manual review |

### Package briefs (for implementer agents)

#### P1 — Success formatters (D3 gate)

- **Goal:** Restore CLI trust; eliminate false error output on success for validate/resolve/logs families.
- **Deliverables:** Formatter functions; registry keys `("config","validate")`, `("app","validate")`, `("cli","resolve")`, `("host","logs")`; optional safe default for other `ok` results; tests through `main()`/`foundry.sh`.
- **Out of scope:** Formatters for every command (spec defers phase 2).
- **Touchpoints:** [foundry.py](../../../.cursor/foundry/cli/foundry.py), tests.

#### P2 — Host spawn packaging

- **Goal:** Detached host child imports `foundry_cli` without manual `PYTHONPATH` from app cwd.
- **Deliverables:** Spawn env using resolved CLI/bundle paths; test from tmp app workspace.
- **Out of scope:** Full supervisor / stale PID reaper.
- **Touchpoints:** [host_commands.py](../../../.cursor/foundry/cli/foundry_cli/host_commands.py).

#### P3 — Bridge discovery + detached lifecycle

- **Goal:** Persist bridge metadata per workspace; health check; stop/restart when workspace/port/wrong binding.
- **Deliverables:** State file under `.foundry/`; detached bridge spawn; reconcile API used by `up`.
- **Out of scope:** Multi-bridge load balancing.
- **Touchpoints:** new module, [bridge_commands.py](../../../.cursor/foundry/cli/foundry_cli/bridge_commands.py).

#### P4 — `foundry up`

- **Goal:** One command: resolve workspace → reconcile bridge → start host with adapter env → readiness summary → exit 0 when ready.
- **Deliverables:** `cmd_up`; `--json` schema (workspace, bridge, host process, health, adapter with configured/reachable semantics); `--foreground` with signal handling; idempotent paths; align canonical `shape --input-file` for first-run test.
- **Out of scope:** `foundry ready` command (D4); full `host status` refactor (P5).
- **Touchpoints:** [parser.py](../../../.cursor/foundry/cli/foundry_cli/parser.py), [foundry.py](../../../.cursor/foundry/cli/foundry.py), `up_commands.py`, integration test matching [gwt-scenario.md](gwt-scenario.md).

#### P5 — Host status model

- **Goal:** Replace overloaded `running` with explicit dimensions in JSON and human output; extract shared readiness helpers from P4 where duplicated.
- **Deliverables:** Schema + formatter; update internal callers.
- **Out of scope:** Replacing `up` summary with `host status` as primary readiness (D4).
- **Touchpoints:** [host/client.py](../../../.cursor/foundry/cli/foundry_cli/host/client.py), [foundry.py](../../../.cursor/foundry/cli/foundry.py).

#### P6 — Status latency

- **Goal:** Record baselines; implement caps; prevent status from blocking on 30s health timeout where inappropriate.
- **Deliverables:** Probe doc or test; shorter status-only timeout; CI or documented probe.
- **Touchpoints:** [timeout_policy.py](../../../.cursor/foundry/cli/foundry_cli/host/timeout_policy.py).

#### P7 — Preflight

- **Goal:** Actionable messages when dependencies missing before `shape` or `host start`.
- **Deliverables:** `preflight_check(workspace) -> result`; wire into `cmd_shape` and `cmd_host_start`.
- **Touchpoints:** [user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py), [host_commands.py](../../../.cursor/foundry/cli/foundry_cli/host_commands.py).

#### P8 — Logs marker + since-start

- **Goal:** Correlate log tail to latest successful start/up.
- **Deliverables:** Marker fields; `--since-start`; human header.
- **Touchpoints:** [discovery.py](../../../.cursor/foundry/cli/foundry_cli/host/discovery.py), [log_reader.py](../../../.cursor/foundry/cli/foundry_cli/host/log_reader.py).

#### P9 — Judgment diagnostics

- **Goal:** Operators see layer (host/bridge/provider) and one recovery hint; JSON carries upstream status.
- **Deliverables:** Structured bridge errors; adapter mapping; tests with mocked HTTP/SDK failures.
- **Touchpoints:** [server.py](../../../.cursor/foundry/cli/foundry_cli/judgment_bridge/server.py), [http_adapter.py](../../../.cursor/foundry/cli/foundry_cli/engine/agent/http_adapter.py).

#### P10 — Documentation

- **Goal:** Runbook first-run path centers on `foundry up`.
- **Deliverables:** Runbook edits; optional `cli docgen` capability row for `up`.
- **Touchpoints:** [operator-runbook.md](../../operator-runbook.md).

### Verifier briefs

#### P1 — verification

- **Must prove:** AC 1 — no `error [` on success; human lines match contract.
- **Commands / probes:** `foundry config validate`, `app validate`, `cli resolve`, `host logs` (fixture log); pytest CLI stdout tests.
- **Regression watch:** JSON unchanged; update `test_format_result_falls_back_to_error_for_unformatted_success` if default ok formatter added.

#### P2 — verification

- **Must prove:** AC 7 — `host start` from clean sibling app without manual `PYTHONPATH`.
- **Commands / probes:** Tmp workspace fixture; assert process starts and health RPC succeeds.
- **Regression watch:** Existing bundle venv `foundry.sh` path still works.

#### P3 — verification

- **Must prove:** AC 4–5 — bridge reconcile and wrong-cwd recovery.
- **Commands / probes:** Start bridge from registry cwd then `up` from app workspace; double `up` idempotency on bridge.
- **Regression watch:** Standalone `bridge start` still works for debug.

#### P4 — verification

- **Must prove:** AC 2–6, 13; GWT judgment after `up` (live or mocked per CI policy).
- **Commands / probes:** Clean sibling fixture: `up --json` → `shape --input-file docs/plans/foundry-up.md`; wrong-cwd bridge; `--foreground` Ctrl+C manual or scripted; win32 spot-check for detach/foreground where feasible.
- **Regression watch:** `host start` / `bridge start` standalone.

#### P5 — verification

- **Must prove:** AC 8 — three dimensions visible; no contradictory single flag.
- **Commands / probes:** `host status` and `host status --json` with host down, up, adapter missing.
- **Regression watch:** [job_host.feature](../../../.cursor/foundry/cli/tests/acceptance/features/job_host.feature) updated.

#### P6 — verification

- **Must prove:** AC 9 — timings under caps in three scenarios (bridge absent / ready / stale discovery).
- **Commands / probes:** Documented probe script outputs; optional timed pytest markers.

#### P7 — verification

- **Must prove:** AC 10 — preflight messages and suggested `foundry up`.
- **Commands / probes:** Host stopped; host up without adapter; JSON fields.

#### P8 — verification

- **Must prove:** AC 11 — header and since-start excludes prior attempt lines.
- **Commands / probes:** Two starts; `--since-start`.

#### P9 — verification

- **Must prove:** AC 12 — layer + hint human; structured `--json` on simulated failure.
- **Commands / probes:** Mocked bridge validation failure; extend [test_judgment_bridge.py](../../../.cursor/foundry/cli/tests/unit/test_judgment_bridge.py).

#### P10 — verification

- **Must prove:** Runbook describes `foundry up` as primary first-run path.
- **Commands / probes:** Manual doc review.

---

## Suggested implementation order

**Canonical package sequence:** P1 → P2 → P3 → P4 → P5 (+ P6) → P7 → P8 → P9 → P10.

### Build order rationale (`up` vs D5)

- **D4** requires v1 readiness on **`foundry up` exit only**; **D5** applies to **`host status`**, not as a prerequisite command surface.
- **P4** therefore ships **`up` readiness JSON** with the process / health / adapter dimensions required by **AC 2** without waiting for **P5**.
- **P5** refactors **`host status`** to the same dimensional model (extract shared helpers from P4 where practical). Some duplication between P4 and P5 is acceptable if P5 consolidates in the same release train.
- **P8** (markers) may start after P4 stable start paths; **P7** (preflight) after P3/P4 stubs exist. **P5** and **P6** may run in parallel after P4.

Detailed steps:

1. **P1** (D3 gate — spec blocks other bundle work until done).
2. **P2** (D6 — reliable host in later packages).
3. **P3** (bridge lifecycle — prerequisite for `up` reconcile).
4. **P4** (core `up` + GWT path + readiness JSON).
5. **P5** + **P6** (status model and latency; parallel after P4).
6. **P7** (preflight).
7. **P8** (markers — after successful start paths stable).
8. **P9** (diagnostics — can parallel with P8).
9. **P10** (docs last).

---

## Test and fixture resources

| Asset | Use |
|-------|-----|
| [test_foundry_entrypoint.py](../../../.cursor/foundry/cli/tests/unit/test_foundry_entrypoint.py) | Formatter / entrypoint behavior |
| [test_host_logs.py](../../../.cursor/foundry/cli/tests/unit/test_host_logs.py) | Log command JSON |
| [foundry_config.feature](../../../.cursor/foundry/cli/tests/acceptance/features/foundry_config.feature) | Config validate / cli resolve |
| [job_host.feature](../../../.cursor/foundry/cli/tests/acceptance/features/job_host.feature) | Host lifecycle |
| [operator_integration_smoke.py](../../../.cursor/foundry/cli/foundry_cli/operator_integration_smoke.py) | Extend for `up` → shape judgment |
| [tests/acceptance/helpers.py](../../../.cursor/foundry/cli/tests/acceptance/helpers.py) | Invoke real CLI in BDD |
| `fixtures/apps/foundry-test` (via smoke) | Minimal app workspace |
| Sibling app fixture pattern (porcelain / tmp workspace) | AC 2–6, GWT |
| [gwt-scenario.md](gwt-scenario.md) | Acceptance narrative |
| [retro.md](retro.md) §5 probes | D11 scenario definitions |

**CI:** Default pipeline should use **mocked bridge** for AC3 where credentials are unavailable; gate **live judgment** in protected workflow or manual probe.

---

## Cross-cutting risks summary

| Risk | Severity | Mitigation |
|------|----------|------------|
| Bridge detached + discovery is new subsystem | High | P3; mirror host discovery patterns |
| Host adapter env frozen at child start | High | P4 spawn env; reconcile restarts host when URL changes (D1) |
| Windows foreground teardown (D10) | Medium | `CREATE_NEW_PROCESS_GROUP`; platform tests |
| JSON schema churn for `host status` | Medium | Additive fields or deprecated `running`; runbook migration |
| 30s default host client timeout inflates status | Medium | P6 measurement before tightening; status-only timeout |
| Auto `host start` in `shape` vs preflight | Medium | P7 coordinates with `_ensure_host` |
| Secrets in bridge env | Medium | Child env only; never log `FOUNDRY_CURSOR_API_KEY` |
| Port conflicts on default bridge port | Medium | Reconcile with ephemeral port + host env update |
| Path mismatch GWT vs docs | Low | Fix in P4 first-run test |
| Live judgment in CI | Low | Mocked default; documented live GWT |

---

## Related artifacts

- [spec.md](spec.md)
- [retro.md](retro.md)
- [gwt-scenario.md](gwt-scenario.md)
- [README](README.md) — bundle index
- [implementation-map-2026-10-13.md](implementation-map-2026-10-13.md) — **superseded archive** (merged into this file)
