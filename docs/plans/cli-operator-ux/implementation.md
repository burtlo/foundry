# CLI operator UX — implementation map

Status: **ready for orchestration** — companion to [spec.md](spec.md). Canonical map for implementer assignment and verifier checklists. Refresh with `/spec-implementation-map @spec.md` after material spec or code changes.

## Spec alignment

### Strengths (spec)

- **Operator outcome** is concrete: verdict-first `up`, symmetric `down`, curriculum help, and a clear **intake vs watch** split for `shape` (default detach vs `--attach`).
- **Decisions D1–D8** map cleanly to CLI surfaces (formatters, parser, `cmd_shape`, `cmd_attach`) without reopening foundry-up reconcile/preflight/Ctrl+C (explicit out of scope).
- **Listed-command table** gives a testable allowlist for default help (D7).
- **Verification plan** names stdout, JSON regression, fixture-led `shape`/`attach`, and dogfood path—fits existing pytest/subprocess patterns under `.cursor/foundry/cli/tests/`.
- **foundry-up dependency** is explicit: human-only delta on `up`; `--json` contract frozen (AC 6).

### Strengths (repository)

- **`foundry up` ships** with readiness payload and dimensions ([up_commands.py](../../../.cursor/foundry/cli/foundry_cli/up_commands.py), [dimensions.py](../../../.cursor/foundry/cli/foundry_cli/readiness/dimensions.py)); JSON shape matches foundry-up intent—safe to change only human `_format_up`.
- **Shutdown primitives exist**: [stop_bridge](../../../.cursor/foundry/cli/foundry_cli/bridge/lifecycle.py), [cmd_host_stop](../../../.cursor/foundry/cli/foundry_cli/host_commands.py); foreground `up` already stops tracked children on Ctrl+C (pattern for `down` scope).
- **Preflight** points operators at `foundry up` ([preflight.py](../../../.cursor/foundry/cli/foundry_cli/readiness/preflight.py)); `_ensure_host` in [user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) fails fast instead of silent partial start.
- **`shape.intake` is engine-owned** with deterministic blocked path (`WORK_PROMPT_MISSING`) in [intake_executor.py](../../../.cursor/foundry/cli/foundry_cli/engine/intake_executor.py); unit coverage in [test_intake_executor.py](../../../.cursor/foundry/cli/tests/unit/test_intake_executor.py).
- **`foundry attach`** already streams ledger JSON and supports detach without cancel ([cmd_attach](../../../.cursor/foundry/cli/foundry_cli/user_cli.py)—reuse for `shape --attach` (D2, AC 24).
- **Host auto-advance loop** exists ([auto_advance.py](../../../.cursor/foundry/cli/foundry_cli/host/auto_advance.py), [server.py](../../../.cursor/foundry/cli/foundry_cli/host/server.py)); integration smoke already uses `--auto-advance` when driving full shape path ([operator_integration_smoke.py](../../../.cursor/foundry/cli/foundry_cli/operator_integration_smoke.py))—wiring from `up` is the gap, not new engine logic.
- **Formatter registry** in [foundry.py](../../../.cursor/foundry/cli/foundry.py) is the right extension point for porcelain `up`/`down`/`shape` copy.

### Gaps and clarifications before build

| Topic | Present state | Spec requirement | Suggested resolution |
|-------|---------------|------------------|----------------------|
| Human `up` | `_format_up` prints `ready=True` and per-dimension `ok=True` lines ([foundry.py](../../../.cursor/foundry/cli/foundry.py) L359–372). No `-v`/`--verbose` on `up` parser. | Verdict-first copy, **Next:** line, compact detail; dimensions only under verbose (AC 1–5). | New formatter module or expand `_format_up`; add `--verbose` on `up` subparser; share dimension rendering with verbose branch. |
| `up --json` | Stable readiness object from `cmd_up`. | Unchanged structure (AC 6). | Snapshot tests only on JSON keys; no payload field renames in this bundle. |
| `foundry down` | No parser entry or handler ([parser.py](../../../.cursor/foundry/cli/foundry_cli/parser.py) ends at `up`). | Mirror `up` scope; idempotent exit 0 (AC 7–9). | `cmd_down` in `up_commands.py` or sibling module: `cmd_host_stop` + `stop_bridge` for workspace; human + JSON envelopes. |
| Root help | `subparsers(required=True)`—bare `foundry` errors; flat argparse order for all commands. | Section headers, listed commands only, journey order (AC 10, D6–D7). | Listed-command metadata module; custom `format_help` or post-parse handler for `foundry`/`-h`; optional `command` not required when showing curriculum. |
| `foundry help` | Not registered in [COMMAND_REGISTRY](../../../.cursor/foundry/cli/foundry.py). | Index + `help -a` + `help <command>` (AC 11–12). | Top-level `help` command with sub-args; delegate to metadata; document unlisted on request. |
| `shape` advance budget | `cmd_shape` calls `_advance_via_host_or_local` with **default `step_budget=8`**—tests expect **`shape.present.gate`** ([test_user_cli_shape.py](../../../.cursor/foundry/cli/tests/unit/test_user_cli_shape.py)). | Stop after successful **intake**; do not block through examine (AC 15). | Advance with stop condition at intake completion (budget=1 + explicit “stop after `shape.intake` sealed” guard, or host RPC `stop_after_node`); return with `intake_complete` fields. |
| Post-intake stdout | `_format_shape` prints `run=… node=… wait=…` only. | Intake ack lines + `run=` + attach/status hints (AC 14–16, D8). | Replace/extend `_format_shape`; add JSON fields for automation (AC 18). |
| Run continues after detach | `cmd_up` → `cmd_host_start` **without** `auto_advance`; GWT smoke **polls `run advance`** ([operator_integration_smoke.py](../../../.cursor/foundry/cli/foundry_cli/operator_integration_smoke.py) L470). | Default happy path: examine runs without operator `run advance` (AC 17). | **P5:** set `auto_advance=True` (and interval) when `up` starts host; document in runbook; extend GWT to assert auto-advance on + no manual advance for intake→examine. |
| Intake failure UX | CLI rejects **empty** `--input`/`--input-file` ([user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py)); engine **blocked** intake returns `intake_status=blocked` with executor-level success. | Non-zero exit, specific message; structured `--json` (AC 19–20). Spec AC text says **`--prompt`**; parser has **`--input`**. | Map blocked intake / preflight failures in `cmd_shape` to `error()` with codes; add **`--prompt` as alias for `--input`** (or amend spec to `--input` only). |
| `shape --attach` | No flag on shape parser. | Intake lines then attach stream through `user_input` (AC 21–24). | `--attach` on shape; after intake handoff call shared attach stream helper from `cmd_attach`. |
| Thin / insufficient prompt | Engine blocks **missing** prompt; non-empty thin text may **pass** deterministic intake. | “Insufficient information” at intake (AC 19, D3). | Confirm engine rules in intake node; if only empty is blocked, extend intake checks or narrow AC in spec—record before **P7**. |
| Doc drift | [cli_docgen.py](../../../.cursor/foundry/cli/foundry_cli/cli_docgen.py) lists flat commands. | Listed help matches operator docs. | Generate or sync from same metadata as **P3**; update [operator-runbook.md](../../operator-runbook.md). |
| CI / GWT | [test_foundry_up_gwt_smoke.py](../../../.cursor/foundry/cli/tests/unit/test_foundry_up_gwt_smoke.py) expects full shape to judgment gate in one CLI invocation. | GWT in spec: shape exits quickly with intake success; examine later. | Split smoke: assert shape exit + hints; separate poll for `shape.examine` with auto-advance. |
| Platform | Bridge/host spawn differs on win32 (`CREATE_NO_WINDOW`, etc.). | Reliable porcelain on operator platforms. | Run `down` idempotency + help golden strings on win32 in verifier matrix. |

### Acceptance criteria traceability

| AC | Present | Delta / work |
|----|---------|----------------|
| 1 | Partial—ready in JSON; human leads with `ready=True`. | **P1** |
| 2 | Missing **Next:** line. | **P1** |
| 3 | Default view dumps all dimensions. | **P1** |
| 4 | No verbose flag on `up`. | **P1** |
| 5 | Not ready uses `READINESS_INCOMPLETE` JSON; human still telemetry-style. | **P1** |
| 6 | JSON readiness structure present (foundry-up). | **P1** verify only |
| 7 | No `down` command. | **P2** |
| 8 | N/A | **P2** |
| 9 | N/A | **P2** |
| 10 | Flat argparse help; all commands visible. | **P3** |
| 11 | No `help` command. | **P4** |
| 12 | No `help -a`. | **P4** |
| 13 | Subcommand `-h` works today. | **P3** keep accurate; regression in **P4** |
| 14 | No intake ack wording. | **P6** |
| 15 | Blocks through present gate (`step_budget=8`). | **P6** |
| 16 | No attach/status hints in shape output. | **P6** |
| 17 | Host from `up` without auto-advance; smoke uses manual advance. | **P5** + **P6** |
| 18 | JSON missing intake handoff fields. | **P6** |
| 19 | Empty input only at CLI; blocked intake not surfaced as CLI error. | **P7** |
| 20 | Partial—preflight JSON exists; blocked intake weak. | **P7** |
| 21 | N/A | **P8** |
| 22 | Attach can stream; shape does not use it. | **P8** |
| 23 | Attach detach behavior exists. | **P8** verify + shape entry |
| 24 | Attach stream is JSON lines—not necessarily question copy. | **P8** (may need event formatting for `user_input`) |
| GWT smoke | — | **P5**, **P6**, **P8** tests |

---

## Repository layout

Work lives in the **Foundry registry CLI bundle** (`.cursor/foundry/cli/`): [foundry.py](../../../.cursor/foundry/cli/foundry.py) dispatch/formatters, [foundry_cli/parser.py](../../../.cursor/foundry/cli/foundry_cli/parser.py) surface, porcelain commands in [user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) and [up_commands.py](../../../.cursor/foundry/cli/foundry_cli/up_commands.py). Plan bundle: `docs/plans/cli-operator-ux/`. Related: [foundry-up/implementation.md](../foundry-up/implementation.md) (upstream `up` mechanics—mostly implemented).

| Path | Role |
|------|------|
| [foundry.py](../../../.cursor/foundry/cli/foundry.py) | `FORMATTER_REGISTRY`, `_format_up`, `_format_shape`, dispatch |
| [foundry_cli/parser.py](../../../.cursor/foundry/cli/foundry_cli/parser.py) | Add `down`, `help`, `up --verbose`, `shape --attach` |
| [foundry_cli/up_commands.py](../../../.cursor/foundry/cli/foundry_cli/up_commands.py) | `cmd_up`; extend for auto-advance; add `cmd_down` |
| [foundry_cli/user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) | `cmd_shape`, `cmd_attach`, intake advance boundary |
| [foundry_cli/readiness/dimensions.py](../../../.cursor/foundry/cli/foundry_cli/readiness/dimensions.py) | Verbose dimension text for `up` |
| [foundry_cli/bridge/lifecycle.py](../../../.cursor/foundry/cli/foundry_cli/bridge/lifecycle.py) | `stop_bridge` for `down` |
| [foundry_cli/host_commands.py](../../../.cursor/foundry/cli/foundry_cli/host_commands.py) | `cmd_host_stop`, start args for auto-advance |
| [foundry_cli/host/auto_advance.py](../../../.cursor/foundry/cli/foundry_cli/host/auto_advance.py) | Background advance after shape detach |
| [foundry_cli/engine/intake_executor.py](../../../.cursor/foundry/cli/foundry_cli/engine/intake_executor.py) | Intake success/blocked semantics |
| [foundry_cli/cli_docgen.py](../../../.cursor/foundry/cli/foundry_cli/cli_docgen.py) | Docs sync with listed metadata |
| [tests/unit/test_foundry_up*.py](../../../.cursor/foundry/cli/tests/unit/) | JSON regression for `up` |
| [tests/unit/test_user_cli_shape.py](../../../.cursor/foundry/cli/tests/unit/test_user_cli_shape.py) | Shape CLI—rewrite for intake handoff |
| [operator_integration_smoke.py](../../../.cursor/foundry/cli/foundry_cli/operator_integration_smoke.py) | End-to-end up→shape path |

---

## Workstreams mapped to decisions

### D5 — Human `up` (delta on foundry-up)

**Present:** Telemetry-style `_format_up`; JSON readiness complete.

**Required:** Verdict-first human copy; verbose dimensions; not-ready operator language + next command.

| Resource | Role |
|----------|------|
| [foundry.py](../../../.cursor/foundry/cli/foundry.py) | Human formatter |
| [parser.py](../../../.cursor/foundry/cli/foundry_cli/parser.py) | `--verbose` on `up` |
| [readiness/dimensions.py](../../../.cursor/foundry/cli/foundry_cli/readiness/dimensions.py) | Failure hints |

**Risks:** Low; avoid changing `cmd_up` JSON keys.

### D4 — `foundry down`

**Present:** Stop via `host stop` + internal `stop_bridge` only.

**Required:** Top-level symmetric stop; idempotent messaging.

| Resource | Role |
|----------|------|
| New `cmd_down` | Orchestrate host then bridge (mirror `up` child scope) |
| [bridge/lifecycle.py](../../../.cursor/foundry/cli/foundry_cli/bridge/lifecycle.py) | Bridge stop |
| [host_commands.py](../../../.cursor/foundry/cli/foundry_cli/host_commands.py) | Host stop |

**Risks:** Medium—bridge started outside workspace / foreign workspace (reuse reconcile semantics from `up`).

### D6, D7 — Grouped help and listed set

**Present:** Alphabetical argparse list; maintainer commands visible by default.

**Required:** Curriculum sections; unlisted hidden from default `-h`.

| Resource | Role |
|----------|------|
| New `foundry_cli/help_catalog.py` (or similar) | Single metadata source |
| [parser.py](../../../.cursor/foundry/cli/foundry_cli/parser.py) | Root help behavior |
| [cli_docgen.py](../../../.cursor/foundry/cli/foundry_cli/cli_docgen.py) | Doc parity |

**Risks:** Drift if metadata not single-sourced; bare `foundry` may need parser `required=False` for AC 10.

### D1, D2, D3, D8 — `shape` intake handoff and `--attach`

**Present:** Full advance to gates; attach is separate command.

**Required:** Intake-only default; handoff lines; optional attach stream; fast failures.

| Resource | Role |
|----------|------|
| [user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) | `cmd_shape`, attach reuse |
| [host/handlers.py](../../../.cursor/foundry/cli/foundry_cli/host/handlers.py) | `run.advance` budget/stop |
| [up_commands.py](../../../.cursor/foundry/cli/foundry_cli/up_commands.py) | Auto-advance on `up` (AC 17) |

**Risks:** High—test suite and GWT assume old blocking shape; attach stream may need human-readable `user_input` lines (AC 22).

---

## Orchestration packages

| ID | Title | Surfaces | Depends on | Primary paths | Verify (AC / tests) |
|----|-------|----------|------------|---------------|---------------------|
| P1 | Porcelain human `up` + verbose | cli-ui, code | — | foundry.py, parser.py, readiness/ | AC 1–6; extend up JSON snapshots |
| P2 | `foundry down` | cli-ui, code | — | up_commands.py, parser.py, foundry.py | AC 7–9; new unit + subprocess tests |
| P3 | Listed metadata + root `-h` | cli-ui, code, docs | — | parser.py, help_catalog.py | AC 10, 13; golden help strings |
| P4 | `foundry help` / `-a` / `<cmd>` | cli-ui, code | P3 | parser.py, foundry.py, help handler | AC 11–12 |
| P5 | `up` starts host with auto-advance | code, config | — | up_commands.py, host_commands.py | AC 17; host status JSON; smoke |
| P6 | Shape intake boundary + handoff output | cli-ui, code | P5 | user_cli.py, foundry.py | AC 14–18; rewrite test_user_cli_shape |
| P7 | Intake validation CLI errors | cli-ui, code | P6 | user_cli.py, intake_executor (read-only) | AC 19–20 |
| P8 | `shape --attach` | cli-ui, code | P6 | user_cli.py, parser.py | AC 21–24; fixture to `user_input` |
| P9 | Runbook + docgen sync | docs, tooling | P3, P4, P2, P6 | operator-runbook.md, cli_docgen.py | Manual dogfood checklist |

### Package briefs (for implementer agents)

#### P1 — Porcelain human `up` + verbose

- **Goal:** Operators see “Foundry is ready” / not-ready verdict without parsing `ok=True`.
- **Deliverables:** `_format_up` rewrite; `--verbose` flag; not-ready copy with next step; JSON untouched.
- **Out of scope:** Readiness dimension definitions, preflight matrix, `host status` reshape.
- **Touchpoints:** `foundry.py`, `parser.py`, optional `readiness/formatting.py`.

#### P2 — `foundry down`

- **Goal:** One command stops host + bridge reconciled by `up` for this workspace.
- **Deliverables:** `cmd_down`, parser/dispatch, `_format_down`, JSON envelope consistent with porcelain.
- **Out of scope:** Stopping unrelated bridges on same port without workspace binding.
- **Touchpoints:** `up_commands.py`, `bridge/lifecycle.py`, `host_commands.py`.

#### P3 — Listed metadata + root `-h`

- **Goal:** Default help shows only listed commands in journey sections (spec table).
- **Deliverables:** Metadata module; custom root help; subcommand `-h` unchanged.
- **Out of scope:** Nested command trees.
- **Touchpoints:** `parser.py`, new catalog module.

#### P4 — `foundry help`

- **Goal:** Git-like `help`, `help -a`, `help shape`.
- **Deliverables:** `cmd_help` (or equivalent); routing in `COMMAND_REGISTRY`.
- **Out of scope:** Concept guides (`help -g`).
- **Touchpoints:** `parser.py`, `foundry.py`, P3 metadata.

#### P5 — Auto-advance from `up`

- **Goal:** After shape detach, host advances through non-human waits without `run advance`.
- **Deliverables:** `cmd_up` passes `auto_advance` into `cmd_host_start`; state visible in `host status`.
- **Out of scope:** Changing auto-advance eligibility rules in engine.
- **Touchpoints:** `up_commands.py`, `host_commands.py`.

#### P6 — Shape intake handoff

- **Goal:** `shape` completes intake, prints run id + watch hints, exits quickly.
- **Deliverables:** Limited advance/stop; `_format_shape` + JSON fields (`intake_status`, hints).
- **Out of scope:** Examine logic changes.
- **Touchpoints:** `user_cli.py`, `foundry.py`, host `run.advance` params.

#### P7 — Intake validation surfacing

- **Goal:** Scripts and humans get actionable errors for rejected intake.
- **Deliverables:** Map blocked intake and validation to non-zero exit; stable error codes in JSON; optional `--prompt` alias.
- **Out of scope:** New LLM intake validation unless spec amended.
- **Touchpoints:** `user_cli.py`, errors.py patterns.

#### P8 — `shape --attach`

- **Goal:** Same intake lines, then attach streaming through questions.
- **Deliverables:** `--attach` flag; refactor shared stream from `cmd_attach`; optional human formatting for question events.
- **Out of scope:** TUI path.
- **Touchpoints:** `user_cli.py`, `parser.py`.

#### P9 — Docs sync

- **Goal:** Runbook and generated docs match porcelain behavior.
- **Deliverables:** `down`, help curriculum, shape async path in [operator-runbook.md](../../operator-runbook.md); docgen uses P3 metadata.
- **Out of scope:** Full CLI reference rewrite.
- **Touchpoints:** docs, `cli_docgen.py`.

### Verifier briefs

#### P1 — verification

- **Must prove:** Ready human stdout starts with verdict phrase; `Next:` present; no dimension lines without `--verbose`; `--json` byte-stable vs existing up tests.
- **Commands / probes:** `foundry up` / `foundry up --verbose` / `foundry up --json` in fixture workspace with mocked dimensions.
- **Regression watch:** `tests/unit/test_foundry_up*.py` JSON assertions.

#### P2 — verification

- **Must prove:** After `up`, `down` stops host and bridge; second `down` exits 0 with clear message; JSON `ok: true`.
- **Commands / probes:** Integration test with mocked bridge + host lifecycle.
- **Regression watch:** Foreground `up` Ctrl+C path still works.

#### P3 — verification

- **Must prove:** `foundry -h` sections match spec listed set; `host`, `run`, `tui` absent; `foundry shape -h` still works.
- **Commands / probes:** Subprocess capture stdout; compare to golden file.
- **Regression watch:** Parser still registers all commands for dispatch.

#### P4 — verification

- **Must prove:** `foundry help` equals curated index; `foundry help -a` includes `host`, `run`, `dev`; `foundry help shape` documents shape flags.
- **Commands / probes:** Subprocess golden tests.
- **Regression watch:** No collision with future nested `help` subcommands.

#### P5 — verification

- **Must prove:** After `up`, `host status` shows `auto_advance=true`; shape intake-only run reaches `shape.examine` without CLI `run advance` within timeout.
- **Commands / probes:** Extend operator smoke or dedicated test with mock adapter.
- **Regression watch:** Tests that pass `--no-auto-advance` to host still valid.

#### P6 — verification

- **Must prove:** `shape --input-file` exits 0 in few seconds; stdout contains intake success + `run=` + attach/status hints; does not wait at present gate.
- **Commands / probes:** Rewrite `test_user_cli_shape` first scenario; mock/stub examine if needed.
- **Regression watch:** `answer`/`decide` tests still use `--no-host`/`--local` paths.

#### P7 — verification

- **Must prove:** Empty file → non-zero + clear message; blocked intake path → non-zero JSON code.
- **Commands / probes:** Fixture prompts from `test_intake_executor` blocked case via CLI.
- **Regression watch:** Happy-path intake still exits 0.

#### P8 — verification

- **Must prove:** `--attach` prints intake lines then streams; fixture parked on `user_input` shows question text; Ctrl+C detach message; run continues.
- **Commands / probes:** Reuse stub agent questions from `test_user_cli_shape` answer test.
- **Regression watch:** `cmd_attach` standalone unchanged.

#### P9 — verification

- **Must prove:** Runbook documents `down`, help, shape handoff; docgen build succeeds.
- **Commands / probes:** `dev docs` or doc build smoke; manual checklist from spec verification plan.

---

## Suggested implementation order

**Canonical package sequence:** P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 → P9

### Build order rationale

1. **P1 / P2** are independent porcelain wins (readiness copy and lifecycle symmetry) and do not block shape work.
2. **P3 → P4** should share one metadata module so default `-h` and `help` never diverge (D6).
3. **P5 before P6** satisfies AC 17: intake-only `shape` is insufficient if the host never auto-advances (today’s GWT explicitly calls `run advance`).
4. **P6 before P7/P8** establishes the default detach contract; failures and attach extend the same `cmd_shape` path.
5. **P9** last to describe shipped behavior.

---

## Test and fixture resources

| Asset | Use |
|-------|-----|
| [test_foundry_up.py](../../../.cursor/foundry/cli/tests/unit/test_foundry_up.py) | JSON `cmd_up` contract |
| [test_user_cli_shape.py](../../../.cursor/foundry/cli/tests/unit/test_user_cli_shape.py) | Shape porcelain—replace intake-blocking expectations |
| [test_intake_executor.py](../../../.cursor/foundry/cli/tests/unit/test_intake_executor.py) | Blocked intake engine semantics |
| [shape_flow_helpers.py](../../../.cursor/foundry/cli/tests/unit/shape_flow_helpers.py) | Workspace fixtures |
| [operator_integration_smoke.py](../../../.cursor/foundry/cli/foundry_cli/operator_integration_smoke.py) | Up→shape dogfood—split shape exit vs later examine |
| [test_preflight.py](../../../.cursor/foundry/cli/tests/unit/test_preflight.py) | Preflight error shape |

**CI:** Prefer mocked bridge/host for help/shape unit tests; keep live GWT in xdist group `foundry_up_gwt_smoke` with updated assertions. **win32:** add `down` + help subprocess tests on Windows agents when available.

---

## Cross-cutting risks summary

| Risk | Severity | Mitigation |
|------|----------|------------|
| Shape behavior change breaks existing tests/smoke | High | Land P5+P6 with test rewrites in same PR wave |
| AC 17 without auto-advance on `up` | High | P5 explicit; verify in smoke |
| `--prompt` vs `--input` in spec | Low | `--prompt` alias in P7 or spec edit |
| Thin prompt validation only in engine | Medium | Clarify in P7 before coding extra rules |
| Attach stream JSON vs human questions | Medium | P8 may add formatter for `user_input` events |
| Help metadata drift from parser | Medium | Single `help_catalog.py` source |
| foundry-up map stale vs repo | Low | This bundle assumes `up` JSON shipped; only human delta |

---

## Related artifacts

- [spec.md](spec.md)
- [retro.md](retro.md)
- [foundry-up/spec.md](../foundry-up/spec.md) · [foundry-up/implementation.md](../foundry-up/implementation.md)
- [organized-cli.md](../organized-cli.md)
- [operator-runbook.md](../../operator-runbook.md)
