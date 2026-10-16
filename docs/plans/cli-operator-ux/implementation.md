# CLI operator UX — implementation map

Status: **ready for orchestration** — companion to [spec.md](spec.md). Canonical map for implementer assignment and verifier checklists. **Full refresh** against spec revision 2026-10-15. **Baseline P1–P9** orchestrated and verified ([orchestration-progress.md](orchestration-progress.md)); **remaining work P10–P15** (interactive attach, ledger automation, docs/tests). Refresh with `/spec-implementation-map @spec.md` after material spec or code changes.

## Spec alignment

### Strengths (spec)

- Clear **two-surface split**: interactive `attach` vs **`ledger`** for automation (D9–D10); v1 defers collapsed timeline (reduces UI risk).
- **D1–D8** already delivered in baseline packages; spec revision **does not reopen** up/down/help/shape intake contracts—only the **watch path** changes.
- **Verification plan** names Textual headless tests, non-TTY attach, and ledger pointers—maps to existing `test_tui.py` plus new attach/ledger tests.
- **Assumption** that `run.context` (markdown) backs history is satisfied by host RPC ([handlers.py](../../../.cursor/foundry/cli/foundry_cli/host/handlers.py) `run.context` with `format=markdown`).

### Strengths (repository)

- **Porcelain foundation shipped:** verdict-first `up` ([readiness/formatting.py](../../../.cursor/foundry/cli/foundry_cli/readiness/formatting.py)), `down` ([up_commands.py](../../../.cursor/foundry/cli/foundry_cli/up_commands.py), [test_foundry_down.py](../../../.cursor/foundry/cli/tests/unit/test_foundry_down.py)), curriculum help ([help_catalog.py](../../../.cursor/foundry/cli/foundry_cli/help_catalog.py), [test_foundry_root_help.py](../../../.cursor/foundry/cli/tests/unit/test_foundry_root_help.py), [test_foundry_help_command.py](../../../.cursor/foundry/cli/tests/unit/test_foundry_help_command.py)).
- **Shape intake handoff:** `stop_after_advance_reason=intake_complete` in [user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py); human hints in [_format_shape](../../../.cursor/foundry/cli/foundry.py); **`up` enables host auto-advance** via [configure_host_start_for_up](../../../.cursor/foundry/cli/foundry_cli/host_commands.py).
- **Textual operator UI already exists** under [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py): run list, run detail, wait actions (answer/decide/start/advance), `run.context` markdown fetch, Escape **back**, Enter open run, poll for live updates.
- **`ledger show`** implemented ([commands.py](../../../.cursor/foundry/cli/foundry_cli/commands.py) `cmd_ledger_show`, [parser.py](../../../.cursor/foundry/cli/foundry_cli/parser.py)).
- **Textual** in [requirements.txt](../../../.cursor/foundry/cli/requirements.txt); headless mount tests in [test_tui.py](../../../.cursor/foundry/cli/tests/unit/test_tui.py).

### Gaps and clarifications before build

| Topic | Present state | Spec requirement | Suggested resolution |
|-------|---------------|------------------|----------------------|
| **`foundry attach` metaphor** | [cmd_attach](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) **requires** `run`; default path is **JSON line stream** via [stream_run_attach](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) (stderr headers + stdout JSON events). | **Interactive-only** attach; optional run; list when omitted (AC 25–27, D9). | **P11:** route attach to Textual; `run` `nargs='?'`; remove/replace JSON follow as default attach behavior. |
| **`shape --attach`** | [foundry.py](../../../.cursor/foundry/cli/foundry.py) calls `stream_run_attach(..., human_questions=True)` after intake ([test_shape_attach.py](../../../.cursor/foundry/cli/tests/unit/test_shape_attach.py)). | Launch **same interactive UI** as `foundry attach <id>` (AC 21–24). | **P13:** call shared interactive launcher after intake lines. |
| **`foundry tui`** | Separate [cmd_tui](../../../.cursor/foundry/cli/foundry_cli/tui_commands.py) → [run_tui](../../../.cursor/foundry/cli/foundry_cli/tui/app.py); unlisted in help. | Deprecation notice + alias to attach, or remove (AC 32, D7). | **P13:** `cmd_tui` → interactive attach with stderr notice. |
| **Markdown history** | TUI writes raw markdown into `RichLog` (`markup=False`); **latest** `run.context` snapshot; parallel **JSON event log** pane. | Scrollable **rendered** markdown covering **full history v1** (AC 28, D11). | **P12:** Textual `Markdown` (or Rich render) in scroll container; define history composition; de-emphasize raw JSON pane in attach mode. |
| **Pointer on run list** | [RunListScreen](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) opens run on **Enter** only; no row click handler (retro: rows inert on click). | Enter **and** primary pointer activation (AC 27). | **P12:** handle row select / click. |
| **Non-TTY attach** | No `sys.stdout.isatty()` guard in attach. | Non-zero exit + pointer to `ledger show` / `ledger follow` (AC 31). | **P10** + **P11:** TTY check in `cmd_attach`; error copy names ledger commands. |
| **`ledger follow`** | Parser has **`ledger show`** only; streaming logic lives on **attach** (`stream_run_attach`, `run.events` loop). | Automation path for legacy attach JSON/follow (AC 33, D10). | **P10:** add `ledger follow` (move/refactor stream helper); document in `help -a`. |
| **attach `--json` / scripting** | attach supports `--json` / `--no-follow` snapshot+events batch. | Scripts use **ledger**, not attach (AC 33–34). | **P10:** batch read on `ledger show`; deprecate attach JSON streaming with migration message. |
| **Runbook / docgen** | [operator-runbook.md](../../operator-runbook.md) and [cli_docgen.py](../../../.cursor/foundry/cli/foundry_cli/cli_docgen.py) still describe attach as **ledger stream**. | Hints point to attach for humans, ledger for scripts (AC 34). | **P14:** sync runbook, docgen, parser help strings. |
| **Thin prompt at intake** | Engine blocks **missing** prompt; non-empty thin text may still pass deterministic intake ([intake_executor.py](../../../.cursor/foundry/cli/foundry_cli/engine/intake_executor.py)). | “Insufficient information” (AC 19, D3). | Clarify engine/node rules; extend intake only if product requires—else narrow AC. **P15** verifier probe. |
| **Windows flashes** | Retro item; out of spec v1 scope. | — | Separate bundle; note as cross-cutting low priority. |
| **GWT / smoke** | [test_foundry_up_gwt_smoke.py](../../../.cursor/foundry/cli/tests/unit/test_foundry_up_gwt_smoke.py) intake path updated in P6. | Spec GWT: shape exits fast; examine later. | **P15:** re-assert GWT + attach smoke. |

### Acceptance criteria traceability

| AC | Present | Delta / work |
|----|---------|----------------|
| 1–6 | **Shipped** (P1). | **P1** regression only |
| 7–9 | **Shipped** (P2). | **P2** regression only |
| 10–13 | **Shipped** (P3–P4). | **P3–P4** regression only |
| 14–18 | **Shipped** (P5–P6). | **P5–P6** regression only |
| 19–20 | **Shipped** (P7). | **P7** regression; thin-prompt clarification row above |
| 21 | Intake lines printed. | **P13** verify |
| 22 | **Partial** — JSON stream, not UI. | **P13** |
| 23 | Detach/stream behavior exists for JSON path. | **P11–P13** interactive detach semantics |
| 24 | Questions on **stderr** in stream path; not markdown pane. | **P12–P13** |
| 25–27 | **Missing** — attach requires run; no list in attach; pointer gap. | **P11–P12** |
| 28 | **Partial** — markdown fetched but not rendered; history model unclear. | **P12** |
| 29 | **Partial** — wait actions exist in TUI, not wired through attach. | **P11–P12** |
| 30 | Escape back exists in **TUI** `RunDetailScreen`. | **P11–P12** wire through attach entry |
| 31 | **Missing** non-TTY guard. | **P10–P11** |
| 32 | **Missing** tui deprecation. | **P13** |
| 33 | **Partial** — `ledger show` only; follow on attach. | **P10** |
| 34 | Runbook still script-attach friendly. | **P14** |
| GWT smoke | Baseline shape path updated. | **P15** attach + ledger paths |

---

## Repository layout

Porcelain and host client work live in `.cursor/foundry/cli/`. Plan bundle: `docs/plans/cli-operator-ux/`. Upstream lifecycle: [foundry-up/implementation.md](../foundry-up/implementation.md) (mostly implemented; human `up` delta absorbed in P1).

| Path | Role |
|------|------|
| [foundry.py](../../../.cursor/foundry/cli/foundry.py) | Dispatch, `_format_shape`, shape `--attach` hook (today: stream) |
| [foundry_cli/user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) | `cmd_attach`, `stream_run_attach`, `cmd_shape` |
| [foundry_cli/tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) | Textual list/detail UI — evolve into attach plane |
| [foundry_cli/tui/host_client.py](../../../.cursor/foundry/cli/foundry_cli/tui/host_client.py) | Host RPCs for UI |
| [foundry_cli/tui_commands.py](../../../.cursor/foundry/cli/foundry_cli/tui_commands.py) | `foundry tui` entry |
| [foundry_cli/parser.py](../../../.cursor/foundry/cli/foundry_cli/parser.py) | attach/shape/tui/ledger parsers |
| [foundry_cli/commands.py](../../../.cursor/foundry/cli/foundry_cli/commands.py) | `ledger show` |
| [foundry_cli/help_catalog.py](../../../.cursor/foundry/cli/foundry_cli/help_catalog.py) | Listed commands (`attach` listed; `tui` unlisted) |
| [tests/unit/test_shape_attach.py](../../../.cursor/foundry/cli/tests/unit/test_shape_attach.py) | Rewrite for interactive attach |
| [tests/unit/test_tui.py](../../../.cursor/foundry/cli/tests/unit/test_tui.py) | Extend for attach navigation AC |

---

## Workstreams mapped to decisions

### D9–D12 — Interactive attach (spec revision)

**Present:** JSON streaming attach plus parallel **TUI** with richer UI; two metaphors.

**Required:** Single **attach** plane; list ↔ run; markdown history; wait actions; live updates.

| Resource | Role |
|----------|------|
| [user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) | Replace stream default with UI launcher |
| [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) | Product UI |
| [parser.py](../../../.cursor/foundry/cli/foundry_cli/parser.py) | Optional `run`, help text |

**Risks:** High — largest UX change; rewrite attach/shape-attach tests.

### D10 — Automation = ledger

**Present:** Stream loop on attach; `ledger show` static.

**Required:** `ledger follow` for streaming; attach non-TTY points here.

| Resource | Role |
|----------|------|
| [user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) | Extract follow implementation |
| [parser.py](../../../.cursor/foundry/cli/foundry_cli/parser.py) | `ledger follow` subcommand |

**Risks:** Medium — scripts/docs may reference `attach --json`.

### Baseline D1–D8 (complete)

Documented in [orchestration-progress.md](orchestration-progress.md). Regression-only unless spec edits reopen scope.

---

## Orchestration packages

### Baseline (complete — regression)

| ID | Title | Status |
|----|-------|--------|
| P1 | Porcelain human `up` + verbose | **Complete** |
| P2 | `foundry down` | **Complete** |
| P3 | Listed metadata + root `-h` | **Complete** |
| P4 | `foundry help` / `-a` / `<cmd>` | **Complete** |
| P5 | `up` → host auto-advance | **Complete** |
| P6 | Shape intake boundary + handoff output | **Complete** |
| P7 | Intake validation CLI errors | **Complete** |
| P8 | *(superseded scope)* JSON `shape --attach` stream | **Complete** — replaced by **P10–P13** |
| P9 | Runbook + docgen (pre-attach-rev) | **Complete** — refresh in **P14** |

### Remaining work

| ID | Title | Surfaces | Depends on | Primary paths | Verify (AC / tests) |
|----|-------|----------|------------|---------------|---------------------|
| P10 | `ledger follow` + stream migration | code, cli-ui | — | user_cli.py, commands.py, parser.py | AC 31, 33 |
| P11 | Interactive `cmd_attach` entry | code, cli-ui | P10 | user_cli.py, tui/app.py, parser.py, foundry.py | AC 25–27, 30–31 |
| P12 | Attach UI: markdown history + pointer + product layout | cli-ui, code | P11 | tui/app.py | AC 24, 28–29 |
| P13 | `shape --attach` + `tui` deprecation | cli-ui, code | P11 | foundry.py, tui_commands.py, parser.py | AC 21–24, 32 |
| P14 | Docs / docgen / parser help sync | docs, tooling | P10–P13 | operator-runbook.md, cli_docgen.py, parser.py | AC 34 |
| P15 | Verification suite (attach plane) | tooling, ci | P11–P13 | test_tui.py, test_shape_attach.py, new attach tests | Verification plan; GWT |

### Package briefs (for implementer agents)

#### P10 — `ledger follow` + stream migration

- **Goal:** Scripts stream run events without `foundry attach`.
- **Deliverables:** `cmd_ledger_follow` (refactor from `stream_run_attach`); parser subcommand; `--json` line stream; attach stops exposing follow stream (batch or error with migration hint).
- **Out of scope:** Changing ledger event schema.
- **Touchpoints:** `user_cli.py`, `commands.py`, `parser.py`, dispatch in `foundry.py`.

#### P11 — Interactive `cmd_attach` entry

- **Goal:** `foundry attach` and `foundry attach <id>` launch Textual session (list or direct run view).
- **Deliverables:** Shared `run_interactive_attach(workspace, registry, run_id=None)`; TTY check with ledger pointer; parser `run` optional; update attach help string.
- **Out of scope:** New host RPCs.
- **Touchpoints:** `user_cli.py`, `tui/__init__.py`, `parser.py`.

#### P12 — Attach UI: markdown history + pointer

- **Goal:** Run view matches v1 history spec: rendered markdown, scrollable, updates as run progresses; list opens on pointer + Enter.
- **Deliverables:** Markdown rendering widget; revision-driven refresh; row click; attach-mode layout (history-primary); keep wait action panel.
- **Out of scope:** Collapsed per-node timeline (v2).
- **Touchpoints:** `tui/app.py`, possibly `host_client.py`.

#### P13 — `shape --attach` + `tui` deprecation

- **Goal:** After intake stdout, open interactive attach on new run; `tui` prints deprecation and delegates.
- **Deliverables:** Replace `stream_run_attach` hook in `_format_result`; stderr notice for `tui`; parser help for `--attach`.
- **Out of scope:** Removing `tui` command entirely (prefer alias + notice).
- **Touchpoints:** `foundry.py`, `tui_commands.py`, `parser.py`.

#### P14 — Docs / docgen sync

- **Goal:** Operator docs match attach vs ledger split.
- **Deliverables:** Runbook shape/attach sections; `cli_docgen` attach/shape summaries; parser help where needed.
- **Out of scope:** Full CLI reference rewrite.
- **Touchpoints:** `docs/operator-runbook.md`, `cli_docgen.py`.

#### P15 — Verification suite

- **Goal:** Spec verification plan coverage for attach plane.
- **Deliverables:** Headless tests: list mount, Enter + pointer open, back to list; non-TTY attach error; fixture markdown in pane; rewrite `test_shape_attach.py`; GWT smoke alignment.
- **Out of scope:** Live bridge dogfood in CI (manual checklist).
- **Touchpoints:** `tests/unit/`, optional acceptance feature updates.

### Verifier briefs

#### P10 — verification

- **Must prove:** `ledger follow` streams JSON lines; `attach` with piped stdout exits non-zero and mentions ledger; no regression on `ledger show`.
- **Commands / probes:** Subprocess tests with mocked `run.events` / fixture run dir.
- **Regression watch:** Stream tests moved from attach to ledger follow.

#### P11 — verification

- **Must prove:** `attach` no-arg starts list UI (headless); `attach <id>` opens detail; TTY guard.
- **Commands / probes:** `textual` `run_test` patterns from `test_tui.py`.
- **Regression watch:** Dispatch still registers attach; listed help unchanged.

#### P12 — verification

- **Must prove:** Markdown widget renders fixture content; pointer opens run; Escape returns to list without process exit.
- **Commands / probes:** Headless pilot / RowSelected handler tests.
- **Regression watch:** Host client mocks unchanged contract.

#### P13 — verification

- **Must prove:** `shape --attach` invokes launcher with run id after intake lines; `tui` stderr deprecation + same launcher.
- **Commands / probes:** Mock launcher in unit tests; subprocess intake stdout unchanged.
- **Regression watch:** `shape` default still detaches without UI.

#### P14 — verification

- **Must prove:** Runbook attach section describes interactive UI; no “use attach for JSON scripts”; docgen build smoke.
- **Commands / probes:** `test_cli_docgen.py` string guards; manual runbook read.

#### P15 — verification

- **Must prove:** Full pytest slice for attach package; GWT smoke still passes with auto-advance shape path.
- **Commands / probes:** `pytest` attach/tui/shape_attach + gwt group.
- **Regression watch:** P1–P7 porcelain tests remain green.

---

## Suggested implementation order

**Canonical package sequence:** **P10 → P11 → P12 → P13 → P14 → P15**

(P1–P9: no implementation—regression on porcelain changes only.)

### Build order rationale

1. **P10 before P11** — non-TTY attach must point at a real **`ledger follow`** command.
2. **P11 before P12** — entry routing and list/run stack before polish (markdown, pointer).
3. **P13 after P11** — `shape --attach` and `tui` delegate to the same launcher.
4. **P14 after behavior** — docs describe shipped attach/ledger split.
5. **P15** last (or parallel per-package tests with P11–P13).

---

## Test and fixture resources

| Asset | Use |
|-------|-----|
| [test_tui.py](../../../.cursor/foundry/cli/tests/unit/test_tui.py) | Headless Textual patterns |
| [test_shape_attach.py](../../../.cursor/foundry/cli/tests/unit/test_shape_attach.py) | Replace stream expectations |
| [test_host_tui_protocol.py](../../../.cursor/foundry/cli/tests/unit/test_host_tui_protocol.py) | `run.context` / `run.events` |
| [shape_flow_helpers.py](../../../.cursor/foundry/cli/tests/unit/shape_flow_helpers.py) | Shape fixtures |
| [operator_integration_smoke.py](../../../.cursor/foundry/cli/foundry_cli/operator_integration_smoke.py) | Dogfood up → shape → attach |

**CI:** Mock host RPC for attach UI tests; keep live GWT in `foundry_up_gwt_smoke` xdist group. **win32:** add non-TTY attach test (platform-agnostic).

---

## Cross-cutting risks summary

| Risk | Severity | Mitigation |
|------|----------|------------|
| Breaking scripts using `attach` JSON stream | High | P10 migration + stderr notice; docgen P14 |
| Duplicating TUI vs attach codepaths | Medium | Single `run_interactive_attach` |
| “Full history” vs single `run.context` snapshot | Medium | P12 design note in PR; host may aggregate markdown |
| Textual optional import in minimal installs | Low | Same as today’s `tui` — clear error if missing |
| Thin-prompt AC vs engine | Medium | Clarify before expanding P7 |

---

## Related artifacts

- [spec.md](spec.md)
- [retro.md](retro.md)
- [orchestration-progress.md](orchestration-progress.md) (P1–P9 complete)
- [foundry-up/spec.md](../foundry-up/spec.md) · [foundry-up/implementation.md](../foundry-up/implementation.md)
- [organized-cli.md](../organized-cli.md)
- [operator-runbook.md](../../operator-runbook.md)
