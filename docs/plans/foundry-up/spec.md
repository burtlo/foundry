# Foundry Up — trustworthy first-run readiness

Status: **approved specification** — from operator retro interview; approved 2026-10-13 ([README](README.md)).

## Source

- Bundle: [README](README.md)
- Retro: [retro.md](retro.md) — investigations §1–§5 and cross-cutting readiness
- GWT seed: [gwt-scenario.md](gwt-scenario.md)

## Operator outcome

From a sibling application workspace with valid `.foundry/` config, the operator runs **one documented setup action** (`foundry up`), gets a **trustworthy readiness summary** (workspace, bridge, host, adapter), runs **`shape`**, and understands the **next action** without learning bridge/host topology. CLI success output never looks like an error; host status and logs answer “what’s running for *this* attempt?”; judgment failures name the failing layer and how to recover.

## Problem statement

Readiness is **distributed** across commands, terminals, environment inheritance, and background processes. The first useful action (`shape`) fails opaque unless the operator already knows cwd rules, adapter env at **host start**, and which process owns the app workspace. Successful CLI commands sometimes print error-shaped text; host status conflates process, health, and adapter readiness; logs mix attempts; bridge errors hide upstream context.

## Scope

### In scope

1. **`foundry up`** (idempotent, D1/D2/D4)
   - Resolves application workspace from invocation context.
   - Starts or reconciles judgment bridge and host (restart only components that are missing, unhealthy, or misconfigured for workspace/adapter URL).
   - Configures host to use the bridge started/reconciled for this workspace.
   - Default: **detach** — start background processes, print readiness summary (human + `--json`), exit 0 when ready.
   - **`--foreground`**: supervise children, stream logs; **Ctrl+C stops bridge and host started by this `up` invocation** and prints a short shutdown summary (D10).
   - Exit payload is the **only v1 readiness surface** (no separate `ready` / global status command).

2. **CLI human success formatters (ship first, D3)**
   - Before other bundle work ships: human output for successful runs of at least `config validate`, `app validate`, `cli resolve`, `host logs` (and any command sharing the same `_format_result` fallthrough path).
   - **No** `error [None]: None` (or equivalent error formatter) on success.
   - Define a minimal **information contract** per family (read-only validate vs mutating start vs log tail).

3. **Host detached start packaging (D6)**
   - `host start` / `up` must not require caller `PYTHONPATH` for `python -m foundry_cli.host` (or equivalent) to work from a clean sibling app workspace.

4. **Host status model (D5)** — applies to `host status` (not replaced by `up` summary)
   - `--json`: separate fields for **process**, **health**, and **adapter readiness** (no single overloaded `running` semantics).
   - Human: three labeled lines; failure obvious on the first failing dimension.

5. **`host status` latency (D11)**
   - Verification establishes baseline latency with bridge absent, bridge ready, and stale discovery record (retro §5 probe).
   - **v1 AC:** human `host status` completes within **documented caps** derived from baseline (recommendation: ≤ **3s** bridge absent, ≤ **5s** bridge+host ready, ≤ **8s** stale discovery — adjust after probe if baselines differ; caps must be checked in CI or a documented manual probe script).

6. **Preflight (D7)**
   - **`host start`** and **`shape`**: before main work, check dependencies; if host is running, report **observed** adapter configuration vs required; name missing bridge/host/adapter and suggested next command (e.g. `foundry up`).

7. **`host logs` (D8, D12)**
   - Header: log path, current PID if known, tail read timestamp.
   - On successful **`host start` / `up`**: persist a **start marker** (id + timestamp) in discovery/metadata.
   - **`host logs --since-start`** (and/or default tail scoped to latest start when marker exists) shows only lines from that start onward.

8. **Judgment / bridge diagnostics (D9)**
   - On transport success + validation failure or bridge non-2xx: human message names layer (host / bridge / provider) + one recovery hint; `--json` includes upstream/SDK status and structured diagnostic fields.
   - Contract tests against SDK response shapes (preserve `finished` and peers).

9. **Documentation**
   - Update [operator runbook](../../operator-runbook.md) first-run path: `foundry up` as primary; document `--foreground`, idempotent reconcile, and preflight behavior.

### Out of scope

- Steward/chat advice quality (retro explicit exclusion).
- **Stale PID/socket reaper** and full host lifecycle supervisor (D6; idempotent restart of *wrong* components only).
- Dedicated **`foundry ready`** or making **`host status`** the primary readiness summary (D4).
- Startup failure UX beyond packaging (e.g. rich pre-discovery failure banner) unless covered by preflight/marker on **successful** start only (D12 A).
- `foundry-0001` run evaluation / shape blocking UX (other retro).
- Expression language, deferred contract slices, cli-test-speed plans.

## Decisions

| ID | Decision | Rationale | Retro link |
|----|----------|-----------|------------|
| D1 | Idempotent `up` — reconcile; restart only what’s wrong | Avoid restart churn; fix wrong workspace/adapter without full teardown | §1 |
| D2 | Default detach; `--foreground` for debug | Matches today’s multi-terminal ops with optional single-terminal mode | §1 |
| D3 | Ship retro-listed success formatters **before** other bundle features | Restore CLI trust | §2 |
| D4 | Readiness summary only on `up` exit | One setup action; avoid duplicating surfaces in v1 | Cross-cutting |
| D5 | Split process / health / adapter in status | Removes contradictory `running` readings | §3 |
| D6 | Packaging-only host start fix | Narrowest fix for `foundry_cli` import without lifecycle project | §3 |
| D7 | Preflight on `host start` and `shape` | Covers paths that skip `up` or mis-order env | §1 |
| D8 | Log header + since-start tail | Current attempt vs history | §5 |
| D9 | Layered judgment diagnostics human + JSON | Recovery without generic 502 | §4 |
| D10 | Foreground Ctrl+C stops children from this `up` | Clear ownership in foreground mode | §1 |
| D11 | `host status` latency caps after measurement | Address perceived slowness with testable bounds | §5 |
| D12 | Start marker on successful start/up only | Enables D8 without stale-state program | §5 |

## Assumptions

- Registry bootstrap (`just setup`) and app `.foundry/` init remain prerequisites documented in the runbook; `up` does not replace `config init` / `app init`.
- Cursor credentials for judgment remain operator responsibility; `up` does not embed secrets beyond existing bridge/host env conventions.
- Idempotent reconcile may restart a running host when adapter URL or workspace does not match resolved app workspace (D1).
- Latency caps (D11) are finalized when verification baselines are recorded in the bundle or a short probe note.

## Acceptance criteria

1. **Formatters (order gate):** For each of `config validate`, `app validate`, `cli resolve`, `host logs` on success, human stdout contains no error-shaped fallback; output matches the defined contract for that family.
2. **`foundry up` (detach):** From a clean sibling app workspace with valid config and credentials, `foundry up` exits 0 and prints readiness showing **workspace**, **bridge**, **host process**, **host health**, **adapter readiness** (human + `--json`).
3. **GWT judgment:** After successful `foundry up`, `foundry shape --input-file docs/plans/foundry-up.md` (or bundle-equivalent path) **reaches judgment** without manual bridge/host choreography ([gwt-scenario.md](gwt-scenario.md)).
4. **Idempotency:** Second `foundry up` with no config change does not unnecessarily restart healthy, correctly configured bridge/host; if bridge was started from wrong cwd previously, `up` reconciles to app workspace (D1).
5. **Wrong-workspace case:** Starting bridge from registry repo then running `up` from app workspace results in bridge associated with **app** workspace (reconcile or restart).
6. **Adapter env:** `shape` after `up` does not fail with `HOST_ERROR: No agent adapter configured` when `up` reported adapter ready; exporting adapter vars only before `shape` without restarting host is not required when `up` succeeded.
7. **Packaging:** `host start` from clean app workspace without manual `PYTHONPATH` succeeds.
8. **`host status`:** `--json` exposes separate process, health, adapter fields; human shows three labeled lines; no contradictory single `running` flag semantics.
9. **`host status` latency:** Meets documented caps (D11) in verification scenarios (bridge absent / ready / stale discovery).
10. **Preflight:** `shape` with host down reports missing dependency and next step; `shape` with host up but missing adapter reports **running host’s** observed config.
11. **`host logs`:** Header present; after `up`/`host start`, default or `--since-start` omits pre-marker log lines from prior attempts.
12. **Judgment failure:** Simulated bridge validation failure includes layer + hint in human output and upstream/status fields in `--json`.
13. **`up --foreground`:** Ctrl+C stops processes started by that invocation and prints shutdown summary.

## Verification plan

- **Formatter regression:** CLI integration tests through real `foundry.sh` stdout path for listed commands (retro §2 mechanism).
- **First-run script:** Clean sibling app fixture: validate → `up` → `shape` input file → judgment reached.
- **Idempotency / workspace:** Run `up` twice; bridge-from-wrong-cwd then `up` from app.
- **Preflight:** Host stopped; host running without adapter; assert messages and JSON fields.
- **Host logs:** Two starts; assert `--since-start` excludes first attempt’s errors.
- **Status latency:** Record timings (absent / ready / stale); set caps; automate or document repeatable probe.
- **Diagnostics:** Bridge/provider fixture or mocked SDK shape for non-2xx / validation failure.
- **Foreground teardown:** Integration test or documented manual check for Ctrl+C behavior.

## Implementation hints (optional)

- Touchpoints from retro: `bridge_commands.py`, `host_commands.py`, `user_cli.py` (`shape`), `foundry.py` formatters, `host/client.py`, `host/log_reader.py`, `cursor_provider.py`.
- Implement **D3** in a discrete change set before `up` command wiring.
- Readiness `--json` schema should be stable enough for future `foundry ready` without committing that command in v1.
- Start marker: store alongside existing host discovery files under `host/`.

## Deferred / follow-up

- Stale PID/socket cleanup and rich failed-start publishing before discovery (retro §3 broader lifecycle).
- Dedicated `foundry ready` / unified status command (D4).
- Command-specific success formatters beyond retro-listed families (§2 phase 2).
- Shape blocking / `user_input` UX ([foundry-self-workspace retro](../operator-onboarding-foundry-self-workspace-retro.md)).
- `host status` deeper perf optimization beyond caps (if caps met but UX still feels slow).
