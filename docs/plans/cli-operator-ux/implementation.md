# CLI operator UX — implementation map

Status: **ready for orchestration** — companion to [spec.md](spec.md) (approved revision 2026-10-16). Canonical map for implementer assignment and verifier checklists. **P1–P15** shipped against the 2026-10-15 spec ([orchestration-progress.md](orchestration-progress.md)). **Remaining work is P16–P21** (operator projection, human list labels, single-scroll run view, technical context, Ctrl+? help). Refresh with `/spec-implementation-map @spec.md` after material spec or code changes.

## Spec alignment

### Strengths (spec)

- D13–D21 name a single run-view contract: operator history, then the human action in the same scroll, with steward diagnostics behind a header control (D14, D20, D21).
- The verification plan names headless Textual probes that match the dogfood failure: list columns, 80×24 question text, approval order, and Ctrl+?.
- D1–D12 and the porcelain commands are explicitly left in force, so this pass does not reopen `up`, `down`, help, or intake handoff.
- Assumptions already separate `run.context` markdown (technical packet) from the default history, and they name viewport behavior (open at the top; later updates keep the operator’s place).

### Strengths (repository)

- Interactive attach is already the TTY path. [cmd_attach](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) calls [run_interactive_attach](../../../.cursor/foundry/cli/foundry_cli/tui/__init__.py) unless `--json` / `--no-follow`. Non-TTY exits with `ATTACH_NOT_TTY` and names `ledger show` / `ledger follow`. `foundry shape --attach` prints intake lines, then calls `cmd_attach` ([foundry.py](../../../.cursor/foundry/cli/foundry.py)).
- [RunDetailScreen](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) already submits answers, decisions, start, and advance through [HostClient](../../../.cursor/foundry/cli/foundry_cli/tui/host_client.py). Enter and `DataTable.RowSelected` open a run; Escape returns to the list. Those behaviors are covered in [test_tui.py](../../../.cursor/foundry/cli/tests/unit/test_tui.py).
- Steward markdown already exists and should stay the technical packet: [render_context_markdown](../../../.cursor/foundry/cli/foundry_cli/render.py) emits Position, Reads, Allow, Operations, Examination, and Judgment.
- Human step titles already exist on nodes (`title:` in `.cursor/foundry/nodes/*/node.yaml`). Intake text is `state.ticket.raw_input` ([intake_executor.py](../../../.cursor/foundry/cli/foundry_cli/engine/intake_executor.py)). Questions, answers, draft AC, assumptions, and examination decisions live on run state ([examination_state.py](../../../.cursor/foundry/cli/foundry_cli/engine/examination_state.py), [submit.py](../../../.cursor/foundry/cli/foundry_cli/engine/agent/submit.py)). Presentation body is the sealed `presentation.md` artifact ([shape_step_executor.py](../../../.cursor/foundry/cli/foundry_cli/engine/shape_step_executor.py)).
- Textual is a required dependency (`textual>=0.80.0` in [requirements.txt](../../../.cursor/foundry/cli/requirements.txt)). The app does not override the framework command palette, so **Ctrl+P** remains available.

### Gaps and clarifications before build

| Topic | Present state | Spec requirement | Suggested resolution |
|-------|---------------|------------------|----------------------|
| Operator history source | The run view sets `#context-markdown` to the latest `run.context` markdown. That packet is the active visit only, and [assemble_context](../../../.cursor/foundry/cli/foundry_cli/context.py) keeps state keys the node `reads`. `shape.examine` does not read `clarifying_answers` or `config.shape.work_prompt`. `agent.result.accepted` ledger payloads omit the result body; the summary lives on the snapshot’s accepted agent result and the examination receipt. | Default history is intake, model response, questions and answers, decisions, and the material for the current human step (D14, AC 28). `run.context` markdown is the technical packet, not that history. | **P17:** a host-only read that returns those slices (ticket `raw_input` or `work_prompt`, examination summary / draft AC / assumptions / examination decisions, `clarifying_questions` plus `clarifying_answers`, `gate.decided` decisions, active gate `prompt`, latest sealed presentation). Compose them in that order. Leave [render.py](../../../.cursor/foundry/cli/foundry_cli/render.py) unchanged. |
| Run list columns | [RunListScreen](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) columns are `run_id`, `status`, `node`, `wait`, `revision`, filled from [list_runs](../../../.cursor/foundry/cli/foundry_cli/run_service.py). | Columns **Run ID**, **Current step**, **Needs**. Needs is **Answers**, **Approval**, or **Agent** for those waits (D17, AC 25). Current step is the human step title. Host RPC values stay unchanged. | **P16:** format at the UI boundary. Map `wait_kind` in the screen. Resolve **Current step** from the node `title` in the local registry (`active_node_id` → `node.yaml`). Do not add fields to `run.list`. |
| Side rail | `#main-panels` is a horizontal split. History is one scroll; `#actions-panel` is a second scroll, width 40, max 42%. At 80 columns the questions sit in a narrow rail. | One vertical stack: history, then the action at full width (D13, D21, AC 29). Three long questions at 80 columns can each be scrolled into view. | **P18:** one `VerticalScroll` for history and the action. Drop the side rail. |
| Run-view header | Textual `Header` plus `#run-summary`: `run=`, `phase=`, `status=`, `node=`, `revision=`, `wait=`. | Header shows run id, human current-step title, and whether the run needs answers or approval (D16, AC 33). Revision, visit id, phase, and raw node id stay in technical context. | **P19:** replace the summary line. Reuse the P16 label helpers. |
| Technical context | Steward markdown is always visible and titled “Run history”. There is no header control. | Off when the run view opens. A **Show technical context** control appends revision, visit id, phase, raw node id, and the steward sections after the action (D20, AC 34). | **P19:** toggle defaults off; when on, mount the existing markdown packet after the action section in the same scroll. |
| Help | List footer bindings are Refresh and Quit. Run view adds Back, Advance, Start. No Ctrl+? panel. | **Ctrl+?** opens a short help panel (navigation, palette, technical-context control). Footer shows **Help Ctrl+?** beside that screen’s common actions (D18, D19, AC 35). **Ctrl+P** stays the palette shortcut. | **P20.** If Textual’s `Footer` splits key from description, add an explicit footer label so the visible text is **Help Ctrl+?**. |
| Viewport | History and actions scroll independently. Markdown replacement has no recorded scroll-to-top or preserve-offset behavior. | The view opens at the top of the history. Later history updates do not move the viewport. Focusing a control scrolls it into view (D21 and assumptions). | **P18:** on first paint, scroll the shared container to the top. On later updates, restore the prior offset unless the focused control must move into view. |
| Needs when the wait is not one of the three named kinds | Empty `wait_kind` is rendered as an empty cell. `operator` waits exist (blocked intake). | Any other wait uses a short human label. The raw wait kind is not the cell text. A null wait is not named. | **P16 default:** `user_input` → **Answers**, `decision` → **Approval**, `agent` → **Agent**, `operator` → **Action**, null → **—**. Any other kind gets a short word that is not the protocol token. |
| Runbook still describes the old pane | [operator-runbook.md](../../operator-runbook.md) calls the run view a “scrollable markdown history”. Scripts are already pointed at ledger (AC 38). | Operator-facing attach copy should match the operator projection. | **P21:** update the interactive-attach section only. |

### Acceptance criteria traceability

| AC | Present | Delta / work |
|----|---------|----------------|
| 1–6 | Shipped (P1). Verdict-first human `up`. | Regression only |
| 7–9 | Shipped (P2). `foundry down`. | Regression only |
| 10–13 | Shipped (P3–P4). Grouped help. | Regression only |
| 14–20 | Shipped (P5–P7). Intake handoff and intake errors. | Regression only |
| 21 | Shipped. Intake lines print before attach. | Regression only |
| 22 | Shipped entry. `shape --attach` launches the same Textual app as `foundry attach <id>`. | The UI that opens is **P18–P20** |
| 23 | Shipped. Leaving attach does not stop the run; attach reopens the run view. | History content when reopened is **P17–P18** |
| 24 | **Partial.** Attach opens, but the scroll is the steward packet and questions are in the side rail. | **P17**, **P18** |
| 25 | **Missing.** Columns are host fields (`run_id`, `status`, `node`, `wait`, `revision`). | **P16** |
| 26–27 | Shipped (P11–P12). Optional run opens the run view; Enter and row selection open it from the list. | Regression only |
| 28 | **Partial.** A markdown pane updates from `run.context`. It is the steward packet, not the operator sequence, and viewport retention is unproven. | **P17**, **P18** |
| 29 | **Partial.** Question labels and inputs exist in `#wait-panel`, clipped beside history. | **P18** |
| 30–32 | Shipped. Escape back, non-TTY ledger pointer, `tui` deprecation notice. | Regression only |
| 33 | **Missing.** Summary line is phase, node id, revision, and raw wait kind. | **P19** (labels from **P16**) |
| 34 | **Missing.** Steward sections are the default pane. | **P19** |
| 35 | **Missing.** No help panel; footer has no **Help Ctrl+?**. | **P20** |
| 36 | **Partial.** A non-human wait omits answer controls, but the pane is still the steward packet and the header is still protocol fields. | **P18**, **P19** |
| 37–38 | Shipped (P10, P14). Ledger show/follow; runbook tells scripts not to use attach. | **P21** refreshes operator wording only |

---

## Repository layout

Porcelain and the Textual client live under `.cursor/foundry/cli/`. This pass changes the attach run list and run view. Host list/get payloads and `render_context_markdown` stay as they are. Plan bundle: `docs/plans/cli-operator-ux/`.

| Path | Role |
|------|------|
| [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) | `RunListScreen`, `RunDetailScreen`, `FoundryTuiApp` — layout, columns, bindings |
| [tui/host_client.py](../../../.cursor/foundry/cli/foundry_cli/tui/host_client.py) | Host RPCs for the UI, including `run.context` json/markdown |
| [render.py](../../../.cursor/foundry/cli/foundry_cli/render.py) | Steward markdown packet (technical context only) |
| [context.py](../../../.cursor/foundry/cli/foundry_cli/context.py) | Visit-scoped context assembly; grant-filtered reads |
| [run_service.py](../../../.cursor/foundry/cli/foundry_cli/run_service.py) | `list_runs` / `get_run` field set |
| [run_labels.py](../../../.cursor/foundry/cli/foundry_cli/run_labels.py) | Phase label only (`shape`, `execute`, …) — not the node title |
| [nodes/shape.examine/node.yaml](../../../.cursor/foundry/nodes/shape.examine/node.yaml) | Human step titles (`title:` on each node) |
| [user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) | `cmd_attach`, non-TTY copy, ledger follow |
| [foundry.py](../../../.cursor/foundry/cli/foundry.py) | `shape --attach` handoff after intake lines |
| [tests/unit/test_tui.py](../../../.cursor/foundry/cli/tests/unit/test_tui.py) | Headless list, navigation, wait-panel tests |
| [operator-runbook.md](../../operator-runbook.md) | Operator attach description |

---

## Workstreams mapped to decisions

### D17 — Human run-list columns

**Present:** `RunListScreen.on_mount` adds columns `run_id`, `status`, `node`, `wait`, `revision` and fills them from `list_runs` (`run_id`, `status`, `active_node_id`, `wait_kind`, `revision`).

**Required:** **Run ID**, **Current step** (node title), **Needs** (**Answers** / **Approval** / **Agent**, or another short human label).

| Resource | Role |
|----------|------|
| [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) | Column headers and cell text |
| [run_service.py](../../../.cursor/foundry/cli/foundry_cli/run_service.py) | Unchanged list payload |
| [nodes/shape.examine/node.yaml](../../../.cursor/foundry/nodes/shape.examine/node.yaml) | Example title: “Shape examination — draft AC and clarifying questions” |

**Risks:** A missing `node.yaml` title must fall back to a short human phrase. Long titles will clip in the table; that matches the spec (no extra columns, no color).

### D14 — Operator history projection

**Present:** `_apply_context_markdown` writes `run.context` markdown into the pane titled “Run history”. On a `shape.examine` user-input wait the JSON packet can include `ticket`, `draft_ac`, `clarifying_questions`, `assumptions`, and `examination_decisions`, and it omits stored answers. On `shape.present.gate` the packet’s decision material is `presented_ac`, the presentation artifact, and the gate prompt — not the earlier intake and Q&A.

**Required:** One projection in operator order: what was submitted, what the model concluded, questions and answers, decisions, and the material for the current human step. Steward headings stay out of this projection.

| Resource | Role |
|----------|------|
| [engine/intake_executor.py](../../../.cursor/foundry/cli/foundry_cli/engine/intake_executor.py) | `ticket.raw_input` |
| [engine/agent/submit.py](../../../.cursor/foundry/cli/foundry_cli/engine/agent/submit.py) | Examination fields on state; accepted result not copied into the ledger payload |
| [engine/shape_step_executor.py](../../../.cursor/foundry/cli/foundry_cli/engine/shape_step_executor.py) | Examination summary markdown and `presentation.md` |
| [engine/examination_state.py](../../../.cursor/foundry/cli/foundry_cli/engine/examination_state.py) | `clarifying_answers` |
| [engine/gates.py](../../../.cursor/foundry/cli/foundry_cli/engine/gates.py) | `gate.decided` payload `decision` |
| [render.py](../../../.cursor/foundry/cli/foundry_cli/render.py) | Remains the technical packet |

**Risks:** Building the projection only from the active `run.context` JSON will drop intake and prior answers on later gates. The new read has to see snapshot state and sealed artifacts while the TUI stays a host client.

### D13, D15, D21 — One scroll, history then action

**Present:** Horizontal split. Wait widgets (question `Label` + `Input`, decision `Button`s, execute start) mount in `#wait-panel`. The history scroll does not contain those controls. The screen opens on whatever the markdown widget shows first; there is no shared scroll offset.

**Required:** The run view opens at the top of the operator history. The action is the next full-width section. Approval material is in the history; approval controls follow. Narrow terminals use the same stack. New history does not jump the viewport. Focusing a control scrolls it into view. When the run does not need the operator, there is no answer or approval section.

| Resource | Role |
|----------|------|
| [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) | `compose`, `DEFAULT_CSS`, `_rebuild_wait_panel` |
| [tests/unit/test_tui.py](../../../.cursor/foundry/cli/tests/unit/test_tui.py) | Today asserts the fixture steward markdown is `#context-markdown` |

**Risks:** `test_run_detail_shows_fixture_context_markdown` encodes the old pane. Wait-panel tests mount controls by id; those ids can stay, but the parent must be the shared scroll.

### D16, D20 — Header and technical context

**Present:** Protocol fields are always on screen. Steward sections are the history body. `get_run` returns `phase`, `active_visit_id`, `active_node_id`, and `revision`, which is the right technical payload and the wrong default header.

**Required:** Header is run id, human step title, and the Needs label. Technical context is off on open. Turning it on appends those protocol fields and the steward sections after the action section.

| Resource | Role |
|----------|------|
| [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) | `#run-summary`, markdown mount |
| [tui/host_client.py](../../../.cursor/foundry/cli/foundry_cli/tui/host_client.py) | `run_context_markdown` stays the toggle payload |
| [run_labels.py](../../../.cursor/foundry/cli/foundry_cli/run_labels.py) | Phase stays inside technical context |

**Risks:** Fetching markdown on every poll and applying it only when the toggle is on. When the toggle is off, a poll must not mount those headings.

### D18, D19 — Ctrl+? help

**Present:** Screen bindings drive the footer. There is no help modal. Ctrl+P is the Textual default palette and is not mentioned on screen.

**Required:** Ctrl+? on the list and the run view opens a panel covering arrows, Enter/click, back, refresh, quit, how to open the command palette, and the technical-context control. The footer shows **Help Ctrl+?** beside that screen’s common actions (list: Refresh, Quit; run view: back, and advance or start where those actions exist).

| Resource | Role |
|----------|------|
| [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) | `BINDINGS` on `RunListScreen` and `RunDetailScreen` |

**Risks:** Binding the chord `ctrl+question_mark` without taking Ctrl+P. Footer widget text may not match the spec string unless it is set explicitly.

---

## Orchestration packages

| ID | Title | Surfaces | Depends on | Primary paths | Verify (AC / tests) |
|----|-------|----------|------------|---------------|---------------------|
| P16 | Human run-list labels | code, cli-ui | — | `tui/app.py`, new label helper, `test_tui.py` | AC 25 |
| P17 | Operator history projection | code | — | new projection module, host read used by the TUI, unit tests | AC 28 source text; D14 |
| P18 | Single-scroll run view | code, cli-ui | P17 | `tui/app.py`, `test_tui.py` | AC 24, 28, 29, 36 (layout) |
| P19 | Header and technical context | code, cli-ui | P16, P18 | `tui/app.py`, `render.py` (consume only) | AC 33, 34, 36 (header) |
| P20 | Ctrl+? help panel | code, cli-ui | P19 | `tui/app.py`, `test_tui.py` | AC 35 |
| P21 | Attach runbook wording | docs | P18, P20 | `docs/operator-runbook.md` | AC 38 still holds; operator section matches the new view |

P16 and P17 have no dependency on each other. A single-threaded run still uses the sequence below.

### Package briefs (for implementer agents)

#### P16 — Human run-list labels

- **Goal:** The run list speaks in operator language.
- **Deliverables:** Columns **Run ID**, **Current step**, **Needs**. Needs map as in the gaps table (`Answers`, `Approval`, `Agent`, `Action`, `—`). Current step is the node `title` resolved locally from `active_node_id`; host `run.list` payload unchanged. Shared helpers importable by the run-view header.
- **Out of scope:** Run-view layout, history body, help panel, color, status, revision columns.
- **Touchpoints:** `RunListScreen` in [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py); registry node load; [test_tui.py](../../../.cursor/foundry/cli/tests/unit/test_tui.py).

#### P17 — Operator history projection

- **Goal:** A pure projection of the operator sequence, independent of the steward packet.
- **Deliverables:** Ordered sections for intake (`ticket.raw_input` or work prompt), model response (examination summary, otherwise draft AC / assumptions / examination decisions), questions with any stored answers, prior decisions (`gate.decided`), and the current human step (open question text is not repeated as the only body — the action section owns the live controls; gate prompt and presentation markdown are the approval material). A host read the TUI can call so this does not require the active node’s `reads` list. No steward headings in the projection.
- **Out of scope:** Widget layout, header toggle, list columns, changes to `render_context_markdown`.
- **Touchpoints:** New module under `foundry_cli/tui/` or `foundry_cli/`; host handler/client only as far as needed to return the slices; fixture unit tests with a snapshot that includes ticket, examination state, answers, and a presentation artifact.

#### P18 — Single-scroll run view

- **Goal:** History, then the human action, in one full-width scroll.
- **Deliverables:** Remove the horizontal split and the “Run history” title on the steward packet. Mount the P17 projection first and the existing wait widgets second, inside one scroll. Open at the top. Preserve scroll offset when a poll refreshes history. Focusing an answer or decision control scrolls it into view. No answer or approval section when the wait is not `user_input` or `decision` (execute-start stays the action for that decision node, as today). `shape --attach` needs no new launcher; it already opens this screen.
- **Out of scope:** Header copy, technical-context toggle, help panel, list columns.
- **Touchpoints:** `RunDetailScreen.compose`, CSS, and wait-panel mount in [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py). Update `test_run_detail_shows_fixture_context_markdown` so it asserts the projection, not the steward packet.

#### P19 — Header and technical context

- **Goal:** The header identifies the run in operator language, and steward diagnostics are opt-in.
- **Deliverables:** Header (or the line under it) shows run id, human step title, and Needs. It does not show revision, visit id, phase, or raw node id while technical context is off. **Show technical context** is off on open. Turning it on appends those fields and the current `run.context` markdown after the action section. Turning it off removes that block. Polls do not reveal it when the control is off.
- **Out of scope:** Rewriting `render_context_markdown`, list columns, help copy.
- **Touchpoints:** [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py), [host_client.py](../../../.cursor/foundry/cli/foundry_cli/tui/host_client.py) `run_context_markdown`, P16 label helpers.

#### P20 — Ctrl+? help panel

- **Goal:** The shortcut the footer names is the help the operator gets.
- **Deliverables:** Ctrl+? on the list and the run view opens a short panel: arrows, Enter/click, back, refresh, quit, how to open the command palette (Ctrl+P), and the technical-context control. Footer text **Help Ctrl+?** beside that screen’s common actions. Ctrl+P still opens the palette.
- **Out of scope:** Replacing the command palette, concept guides, semantic color.
- **Touchpoints:** Bindings and a small modal in [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py).

#### P21 — Attach runbook wording

- **Goal:** The runbook describes the operator view the CLI now opens.
- **Deliverables:** Update the interactive-attach section of [operator-runbook.md](../../operator-runbook.md) so it describes operator history, the action below it, technical context on request, and Ctrl+?. Keep the script rule: automation uses ledger, not attach.
- **Out of scope:** Help taxonomy, `up` / `down` chapters, engine docs.
- **Touchpoints:** [docs/operator-runbook.md](../../operator-runbook.md).

### Verifier briefs

#### P16 — verification

- **Must prove:** A `user_input` row shows **Answers**, a `decision` row shows **Approval**, an `agent` row shows **Agent**. Headers are **Run ID**, **Current step**, **Needs**. Current step is the node title, not `shape.examine`. Status and revision are not columns. `run.list` JSON shape is unchanged.
- **Commands / probes:** Headless Textual test in `tests/unit/test_tui.py` with a mocked `list_runs` row. A unit test for the Needs map including null and `operator`.
- **Regression watch:** Enter and row-selection still open the run (`test_run_list_enter_opens_run_detail`, `test_run_list_row_selected_opens_run_detail`).

#### P17 — verification

- **Must prove:** Given a fixture with known intake text, an examination summary, one answered question, and one gate decision, the projection contains that text in D14 order and does not contain headings `## Position`, `## Examination`, `## Judgment`, `## Allow`, `## Operations`.
- **Commands / probes:** Unit test on the projection function with an in-memory snapshot and artifact body. No Textual required.
- **Regression watch:** `foundry run context --markdown` still returns the steward packet (`render_context_markdown` callers and docgen samples).

#### P18 — verification

- **Must prove:** On a three-question `user_input` fixture at 80×24, the view opens at the top of the history; intake and the model response are present before the inputs; each question’s full text can be scrolled into view; inputs are in the same scroll as the history, not a side rail. An approval fixture shows decision material in the history and controls after it. A non-human wait has no answer or approval section. A second history update does not move the scroll offset away from the operator’s place.
- **Commands / probes:** `app.run_test(size=(80, 24))` in `tests/unit/test_tui.py`. Assert absence of `#actions-panel`. Assert question strings are in the shared scroll.
- **Regression watch:** Submit-answers, decide, and execute-start button ids still work (`test_wait_panel_*`). Escape still returns to the list.

#### P19 — verification

- **Must prove:** On open, the header shows run id, human step title, and Needs, and the rendered tree does not include `## Position` or `revision=`. Activating the header control appends the steward packet after the action section, including revision, visit id, phase, and raw node id. Deactivating removes it. AC 36: no human wait still shows that header plus history only.
- **Commands / probes:** Headless run view with a markdown fixture that contains `## Examination`. Query the tree before and after the control.
- **Regression watch:** P18 scroll order still holds when the toggle is off. `run.context` markdown used by `foundry run context --markdown` is unchanged.

#### P20 — verification

- **Must prove:** Ctrl+? on the list and on the run view opens a panel that mentions the command palette and the technical-context control. The footer on both screens includes **Help Ctrl+?**. Ctrl+P still opens the palette. List footer also offers Refresh and Quit; run-view footer also offers Back.
- **Commands / probes:** `pilot.press` for the help chord and for `ctrl+p` in `tests/unit/test_tui.py`.
- **Regression watch:** `q` still quits. Escape still goes back from the run view when the help panel is closed.

#### P21 — verification

- **Must prove:** The interactive-attach section describes operator history, the action in the same scroll, technical context, and Ctrl+?. It still says scripts must use `ledger show` / `ledger follow` and must not use attach for automation.
- **Commands / probes:** Read [operator-runbook.md](../../operator-runbook.md) sections “Interactive attach” and the script paragraph under it. No CLI behavior change expected; do not require a live host.
- **Regression watch:** Shape hints in the same runbook still name `foundry attach <id>` for humans and `foundry shape --json` for automation (AC 16, AC 38).

---

## Suggested implementation order

**Canonical package sequence:** P16 → P17 → P18 → P19 → P20 → P21

P16 and P17 may run in parallel.

### Build order rationale

1. List labels (P16) and the history projection (P17) do not share widgets. Shipping the list first does not unblock the run view, and shipping the projection first does not change the list. Either order is safe; the sequence above only makes the single-threaded handoff obvious.
2. The single scroll (P18) has to consume the projection. Building the layout first would keep painting the steward packet and then throw that pane away.
3. Technical context (P19) appends after the action section, so the shared scroll from P18 has to exist. The header Needs label should be the same helper as the list, so P16 lands before P19.
4. Help (P20) documents the technical-context control, so it follows P19. The list can show **Help Ctrl+?** before the run view exists, but one package avoids two footer implementations.
5. Runbook copy (P21) follows the UI so the page does not describe a control that is not on screen yet.

---

## Test and fixture resources

| Asset | Use |
|-------|-----|
| [tests/unit/test_tui.py](../../../.cursor/foundry/cli/tests/unit/test_tui.py) | Extend for columns, 80×24 questions, approval order, help chord. Existing navigation and wait-panel tests stay. |
| [tests/unit/test_shape_attach.py](../../../.cursor/foundry/cli/tests/unit/test_shape_attach.py) | Already asserts `shape --attach` calls `run_interactive_attach`. No launcher change. |
| [tests/unit/test_ledger_follow.py](../../../.cursor/foundry/cli/tests/unit/test_ledger_follow.py) | Non-TTY attach pointer. Regression only. |
| Node titles under `.cursor/foundry/nodes/` | Current-step fixtures. |
| In-memory snapshot with `state.ticket.raw_input`, `clarifying_questions`, `clarifying_answers`, and a presentation body | P17 projection fixture. Build it in the test; do not depend on a live `.foundry/runs` directory. |

**CI:** Headless Textual (`app.run_test`) is the same style as the current unit tests and does not need a TTY, a host process, or credentials. Mock `HostClient`. Do not add a live-bridge test for this pass. The spec’s manual pass (`up` → `shape` → attach on a three-question examine wait) stays a manual check after P18–P20, not a CI gate.

---

## Cross-cutting risks summary

| Risk | Severity | Mitigation |
|------|----------|------------|
| Projection built only from grant-filtered `run.context` drops intake and answers on later gates | High | P17 reads snapshot state and sealed artifacts through a host read. Verifier fixture includes a present-gate shape, not only `shape.examine`. |
| Existing test asserts steward markdown is the history pane | Medium | P18 updates that test in the same change. P19 asserts those headings appear only after the control. |
| Markdown refresh jumps the viewport | Medium | P18 stores and restores scroll offset; verifier probes a second update. |
| `run.list` or `render.py` changed while formatting the UI | Medium | P16 and P19 verifier briefs forbid payload and packet changes. |
| Ctrl+? binding swallows Ctrl+P | Low | P20 presses both chords. |
| Windows dogfood vs headless CI | Low | Layout probes use `size=(80, 24)` and do not depend on a real console. Manual confirm remains the spec’s last check. |

---

## Related artifacts

- [spec.md](spec.md)
- [retro.md](retro.md)
- [orchestration-progress.md](orchestration-progress.md) — P1–P15 log; do not restaff those packages
- [README.md](README.md)
- [operator-runbook.md](../../operator-runbook.md)
- [foundry-up/spec.md](../foundry-up/spec.md)
