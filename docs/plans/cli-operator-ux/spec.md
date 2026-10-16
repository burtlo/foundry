# CLI operator UX — porcelain lifecycle, help curriculum, shape intake, interactive attach

Status: **approved specification (revision 2026-10-16)** — from operator retro interview. Revises the 2026-10-15 approved attach surface. Prior **up**, **down**, help, and shape-intake decisions stay in force. [Implementation map](implementation.md) is ready for orchestration (P16–P21). P1–P15 shipped against the 2026-10-15 spec.

## Source

- Bundle: [README](README.md)
- Retro: [retro.md](retro.md) — investigations: 2026-10-16 attach dogfood (run-list labels, hidden command palette, detail metadata, operator history, readable questions), plus the earlier up/down/help/shape items
- Prior approval: 2026-10-15 (D1–D12). This revision adds D13–D21
- Interview: operator decisions 2026-10-16 (history then action in one scroll, operator projection, human list labels, Ctrl+? help, header technical-context control)
- Help taxonomy: operator session [758da1e2-b417-48a1-9815-d1ad326834a2](758da1e2-b417-48a1-9815-d1ad326834a2)
- Git comparison notes: [organized-cli.md](../organized-cli.md)
- Related: [foundry-up/spec.md](../foundry-up/spec.md)

## Operator outcome

After **`foundry up`**, the operator sees **“Foundry is ready”** (or a clear not-ready verdict) and knows what to run next. **`foundry down`** stops the same local stack. **`foundry -h`** and **`foundry help`** read like a short curriculum.

**`foundry attach`** is the only interactive “work on a run” surface. The run list says which runs need the operator. The run view reads as a flow: what they submitted, what the model concluded, and what decision or answers are required. Questions and approval controls are full width below that history in the same scroll. Steward diagnostics stay behind a header control. **Ctrl+?** opens help from a footer label. **`foundry shape`** hands off with **`foundry attach <id>`**. Scripts use **`foundry ledger …`**.

## Problem statement

Human CLI output exposed internal readiness dimensions and implied **`down`** without providing it. Top-level help was flat. **`foundry shape`** blocked through judgment and then exited without the questions.

**`attach`** is now the interactive console, and the 2026-10-16 dogfood showed the remaining gap. The run list projected host fields (`run_id`, `wait`, `user_input`). The run view titled the latest steward packet “Run history,” so Examination, Judgment, Operations, Allow, and the rest occupied the primary pane. Three clarifying questions sat in a fixed side rail and could not be read. The command palette was the help the operator wanted, and nothing on screen pointed to it.

## Scope

### In scope

1. **Human `foundry up` (delta on foundry-up)** — verdict-first stdout; `--json` unchanged; `-v` / `--verbose` for dimension detail.
2. **`foundry down`** — stop everything **`foundry up`** starts for the workspace; idempotent; human + `--json`.
3. **Grouped help** — workflow sections on default `-h`; **`foundry help`** index; **`foundry help -a`** for unlisted commands; nested subcommand `-h` shows real argparse help.
4. **Listed command set** — operator-facing commands in default help (see Decisions).
5. **`foundry shape` intake handoff** — default: complete **`shape.intake`** only, detach, run continues; **`--attach`**: intake lines then interactive attach to the new run.
6. **Intake validation errors** — insufficient input file and/or **`--prompt`** content → actionable human error (and structured `--json`).
7. **Interactive `foundry attach`**
   - Optional **`run`** positional; run **list** when omitted, with human columns **Run ID**, **Current step**, and **Needs**.
   - **Run view** opens at the top of an **operator history** (intake, model response, questions and answers, decisions, and the material for the current human step).
   - On a human wait, **answer or approval controls** are the next full-width section in that same scroll.
   - **Technical context** (revision, visit id, phase, raw node id, steward packet) is off until a **header control** shows it.
   - **Ctrl+?** opens a short help panel; the footer shows **Help Ctrl+?**.
   - **Enter** and **pointer** open a run from the list; a documented back command returns to the list.
   - Live updates while attached.
8. **Non-interactive run inspection** — **`foundry ledger show`** (and **`ledger follow`**) as the automation path.
9. **`foundry tui`** — deprecated alias to **`foundry attach`**, or removed after one release with a migration message.

### Out of scope

- A bottom region that stays on screen while history scrolls (Q9).
- Semantic color on the run list.
- Status and revision as run-list columns.
- Collapsed / expandable per-node timeline (v2).
- Nested command trees (`foundry run …` as the only public API).
- Re-opening foundry-up idempotent reconcile, preflight matrix, or foreground Ctrl+C semantics.
- Engine/steward changes to examine logic beyond what intake already enforces.
- Full IDE-parity chat.
- **`foundry runs`** removal in v1.
- `git help -g`-style concept guides.
- Windows headless subprocess policy.
- Workspace-in-headline **`up`**, positional **`foundry shape`**, and shape **Next:** copy changes beyond the 2026-10-15 approval.

## Decisions

| ID | Decision | Rationale | Retro link |
|----|----------|-----------|------------|
| D1 | Default **`shape`** stops after successful **`shape.intake`**; CLI detaches; run advances asynchronously on host | Intake ack + async run | § `shape` blocks |
| D2 | **Interactive attach** is the watch/work surface; **`shape --attach`** opens it | Subsumes TUI intent | § attach console |
| D3 | Intake failure → clear error (thin/missing input or prompt) | Fail fast at intake | § shape |
| D4 | **`foundry down`** mirrors **`foundry up`** scope | Symmetric lifecycle | § `up` implies `down` |
| D5 | Human **`up`**: **“Foundry is ready”** / not-ready verdict + **Next:** + compact detail; dimensions on **`-v`/`--verbose`** only | Two audiences | § telemetry vs verdict |
| D6 | Grouped **`-h`** + **`foundry help`** + **`foundry help -a`**; leaf parsers use real subcommand help | `runs`/`run` confusion | § workflow help |
| D7 | **Listed** commands in default help; **`tui`** not listed | Curriculum | Interview 2026-10-15 |
| D8 | Post-intake stdout includes **`run=`**, **`foundry attach <id>`**, **`foundry status`** | Next steps | § shape Next |
| D9 | **`attach` = interactive only** | One operator metaphor | Interview 2026-10-15 |
| D10 | **Automation** = **`ledger show`** / **`ledger follow`** | Scripts use ledger | Interview 2026-10-15 |
| D11 | v1 history is a scrollable transcript. **Superseded for content by D14 and D21:** the scroll is the operator projection, then the human action | Operator priority, then 2026-10-16 dogfood | § attach console; § operator history |
| D12 | **`attach`** optional run + **list ↔ run** navigation in one session | Picker in attach | Interview 2026-10-15 |
| D13 | On a human wait the run view is operator history, then the action at full width. Narrow terminals use that same vertical stack | Side rail clipped the questions | § Questions readable |
| D14 | Primary content is intake, model response, questions and answers, decisions, and the material for the current human step. Examination, Judgment, Operations, Allow, Artifacts, Reads, Config, State, Position, Files, and Receipts stay in technical context | Steward packet is debug | § Operator-readable run history |
| D15 | Approval waits use D13 and D14. The flow and the information needed to decide come first; decision controls follow | Human action owns the layout | Cross-cutting §9 |
| D16 | Run-view header shows run id, current step, and whether the run needs answers or approval. Revision, visit id, phase, and raw node id stay in technical context | `v-002` and Position read as debug | § Run identity |
| D17 | Run list columns are **Run ID**, **Current step**, and **Needs**, with short values **Approval**, **Answers**, and **Agent** | List projected the host protocol | § Run-list labels |
| D18 | Help is **Ctrl+?** | Palette was undiscoverable | § Command palette |
| D19 | **Ctrl+?** opens a short help panel (arrows, Enter/click, back, refresh, quit, how to open the command palette, and the technical-context control). The footer shows **Help Ctrl+?** beside that screen’s common actions | Footer makes the shortcut visible | § Command palette |
| D20 | **Show technical context** is a header control on the run view and is listed in the help panel. It is off when the run view opens | Debug on request | § Run identity |
| D21 | The human action is the next section in the same scroll as the history. The view opens at the top of the history. Scrolling down reaches the controls. Focusing a control scrolls it into view | Operator reads the flow, then acts | Q9 |

### Listed commands (default help)

| Section | Commands |
|---------|----------|
| Set up the workspace | `config`, `app` |
| Local Foundry | `up`, `down` |
| Start and watch runs | `shape`, `runs`, `status`, `attach` |
| When the run needs you | `answer`, `decide`, `start` |
| Recover or stop a run | `retry`, `cancel` |

**Unlisted (still callable):** `run`, `visit`, `gate`, `artifact`, `receipt`, `ledger`, `host`, `bridge`, `cli`, `catalog`, `doc`, `dev` — visible via **`foundry help -a`**; **`tui`** alias only if retained.

## Assumptions

- **`shape.intake`** is the engine node that validates “enough information”; acceptance criteria refer to intake success or failure.
- Host continues advancing the run after CLI detach on the default happy path.
- Textual is a required dependency for interactive **`foundry attach`**.
- Operator history may be composed from host context, ledger events, and artifacts. The required order is the operator sequence in D14. **`run.context` markdown is the technical-context packet, not the default history.**
- **Current step** in the header and the list is the human step title.
- **Needs** maps `user_input` → **Answers**, `decision` → **Approval**, `agent` → **Agent**. Any other wait uses a short human label. The raw wait kind is not the cell text.
- When the run does not need the operator, the run view is the header plus operator history. There is no answer or approval section.
- Showing technical context appends that section after the human-action section in the same scroll.
- The command palette remains available. **Ctrl+?** documents how to open it. **Ctrl+P** stays the palette shortcut.
- List footer includes Refresh, Quit, and Help. Run-view footer includes Help plus that screen’s common actions (back, and advance or start where those actions exist).
- New history arrives in the same scroll and does not move the viewport away from the operator’s place.
- **`answer` / `decide` / `start`** remain CLI commands for scripting; attach may call the same host RPCs.
- foundry-up readiness JSON shape remains; only human **`up`** copy changed under D5.
- **`down`** when already stopped exits **0** with a short confirmation.
- Interactive **`attach`** requires a TTY. Non-TTY exits with a pointer to **`ledger`**.

## Acceptance criteria

### `foundry up` (human)

1. When all readiness dimensions pass, human stdout starts with a verdict equivalent to **“Foundry is ready”**.
2. Human stdout includes a **Next:** line (for example **`foundry shape`** when appropriate).
3. Human stdout includes compact operational detail (judgment bridge URL, host PID) without per-dimension `ok=True` lines in the default view.
4. **`foundry up -v`** or **`--verbose`** prints the dimension breakdown.
5. When not ready, human stdout states not ready, names what failed in operator language, and suggests the next command.
6. **`foundry up --json`** structure is unchanged from the foundry-up contract.

### `foundry down`

7. **`foundry down`** exists at top level and stops the same components **`foundry up`** starts or reconciles for the current workspace.
8. **`foundry down`** is idempotent: a second invocation exits **0** with a clear already-stopped message.
9. Human and **`--json`** success envelopes are consistent with other porcelain commands.

### Help

10. **`foundry`** and **`foundry -h`** show section headers and only listed subcommands in journey order, with one-line descriptions.
11. **`foundry help`** shows the same curated index; **`foundry help <command>`** works for listed commands and documents unlisted ones when requested.
12. **`foundry help -a`** lists all top-level subcommands.
13. Positional argparse help for individual subcommands shows that command’s flags and subcommands.

### `foundry shape` — default (no `--attach`)

14. On success, human output confirms the shape request was received and intake succeeded.
15. CLI exits without blocking through **`shape.examine`** or judgment.
16. Human output includes **`run=<id>`**, a line suggesting **`foundry attach <id>`**, and a line suggesting **`foundry status`**.
17. The run continues to subsequent nodes without the operator running **`run advance`**.
18. **`foundry shape --json`** includes run id and intake outcome fields needed for automation.

### `foundry shape` — intake failure

19. When input file and/or **`--prompt`** lack sufficient information for intake, CLI exits non-zero with a specific human message.
20. **`--json`** failure envelope includes a structured reason or code.

### `foundry shape --attach`

21. Prints the same intake received / intake success lines as default **`shape`**.
22. Launches interactive attach to the new run (same UI as **`foundry attach <id>`**).
23. Operator can leave attach; the run continues; **`foundry attach <id>`** reopens the run view with updated history.
24. When the run parks on **`user_input`**, the scroll shows the operator history from the top and, below it, each question in full with its answer control.

### `foundry attach` (interactive)

25. **`foundry attach`** with no run argument opens a run list whose columns are **Run ID**, **Current step**, and **Needs**. **Needs** is **Answers**, **Approval**, or **Agent** for those waits, and a short human label otherwise.
26. **`foundry attach <run_id>`** opens the run view for that run.
27. From the list, **Enter** and primary pointer activation open the run view.
28. The run view opens at the top of a scrollable operator history covering the run to date: intake, model response, questions and answers, decisions, and the material for the current human step. An operator can restate what they submitted, what the model concluded, and what is being asked without turning technical context on. The history updates as the run progresses and keeps the current viewport.
29. When the run needs answers or approval, that action is the next full-width section in the same scroll. Question text wraps. Every control is reachable by keyboard and pointer. Focusing a control scrolls it into view. With three long questions at 80 columns, each question’s full text can be scrolled into view.
30. A documented keybinding or command returns from the run view to the run list without exiting the process.
31. **`foundry attach`** when stdout is not a TTY exits non-zero and names **`foundry ledger show`** / **`ledger follow`**.
32. **`foundry tui`**, if retained, prints a deprecation notice and runs **`foundry attach`**.
33. The run-view header shows run id, the human current-step title, and whether the run needs answers or approval (or the same human **Needs** label when it does not).
34. Technical context is off when the run view opens. The header control reveals revision, visit id, phase, raw node id, and the steward sections (Position, Reads, Config, State, Artifacts, Allow, Files, Receipts, Operations, Examination, Judgment), appended after the action section.
35. **Ctrl+?** on the list and on the run view opens a help panel with arrows, Enter/click, back, refresh, quit, how to open the command palette, and the technical-context control. The footer shows **Help Ctrl+?** beside that screen’s common actions.
36. When the run does not need the operator, the run view is the header and the operator history.

### Non-interactive inspection

37. **`foundry ledger show`** and **`ledger follow`** support **`--json`** and the streaming use cases previously documented for legacy **`attach`**.
38. Operator runbook and **`shape`** hints do not tell scripts to use **`attach`**.

### Given / When / Then (smoke)

```gherkin
Given a workspace where foundry up reports ready
When the operator runs foundry shape --input-file <valid>
Then within a few seconds the CLI exits 0
And stdout contains intake success and run=<id>
And stdout mentions foundry attach and foundry status
And the run later reaches examine without the operator running shape again

Given foundry shape --attach with valid input
When intake completes
Then interactive attach opens on the new run

Given foundry attach with no run argument
When the run list is shown
Then the columns are Run ID, Current step, and Needs
And a user_input wait reads Answers
And a decision wait reads Approval

Given foundry attach <run_id> on a shape.examine wait for clarifying questions
When the run view opens
Then the viewport starts at the operator history
And intake and the model response are visible before any technical section
And scrolling down reaches full question text and answer fields
And technical context is hidden until the header control is used

Given foundry attach <run_id> on an approval wait
When the operator scrolls the run view
Then the information needed to decide appears in the history
And the approval controls follow in that same scroll

Given the operator presses Ctrl+?
When the help panel is open
Then it documents navigation and how to open the command palette
And the footer shows Help Ctrl+?

Given foundry attach <run_id>
When the operator uses back navigation
Then they see the run list again without restarting foundry

Given foundry down after foundry up
When the operator runs foundry down
Then host and bridge started by up for this workspace are stopped
```

## Verification plan

- Headless Textual tests: list columns and **Needs** labels; Enter and pointer open a run; back navigation.
- Fixture run: history contains known intake text and model response; steward section headings are absent until the header control is used.
- **`user_input`** fixture with three long questions at 80×24: wrapped question text is present in the action section, each field can be scrolled into view, and pointer activation still works. The view opens at the top of the history.
- Approval fixture: decision material is in the history; controls follow in the same scroll.
- **Ctrl+?** opens the help panel; footer includes **Help Ctrl+?** on the list and the run view.
- **`attach`** on a non-TTY → error plus a pointer to the ledger commands.
- CLI integration tests already covering human **`up`**, **`down`**, root help, and nested **`run advance -h`** stay green.
- **`shape`**: intake completes without a long block; **`--attach`** opens this run view.
- Regression: **`foundry up --json`** snapshot tests from foundry-up still pass.
- Manual: `up` → `shape` → `attach` on a three-question examine wait; read intake and the model response, scroll to the questions, and answer without opening technical context.

## Implementation hints (optional)

- Evolve the attach run view in [tui/app.py](../../.cursor/foundry/cli/foundry_cli/tui/app.py) to one scroll: operator projection, then the wait section, then technical context when the header control is on.
- Keep [render.py](../../.cursor/foundry/cli/foundry_cli/render.py) as the technical-context packet. Add an operator projection for intake, accepted model output, questions, answers, and decisions.
- Format list rows at the UI boundary in `RunListScreen`; leave host RPC values unchanged.
- Bind **Ctrl+?** to a help panel generated from the same bindings as the footer and the command palette.
- **`cmd_shape`**, **`down`**, curriculum help, and ledger follow stay as implemented for D1–D10 and D12.

## Deferred / follow-up

- Pinned action region that stays on screen while history scrolls.
- Semantic color for **Needs**.
- Status and revision columns on the run list.
- Node-collapsed timeline navigator.
- Concept guides (`foundry help <concept>`).
- **`shape`** positional file or text.
- Workspace path in the **`up`** headline, and shape **Next:** copy beyond D8.
- Windows headless subprocess policy for **`taskkill`** and engine hooks.
