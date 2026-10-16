# CLI operator UX — porcelain lifecycle, help curriculum, shape intake, interactive attach

Status: **approved specification (revision 2026-10-15)** — supersedes 2026-10-14 attach/TUI decisions; [implementation map](implementation.md) refreshed — orchestrate **P10–P15** (baseline P1–P9 shipped).

## Source

- Bundle: [README](README.md)
- Retro: [retro.md](retro.md) — investigations: attach console, TUI list, `runs`/`run` help, Windows flashes, plus prior up/down/help/shape items
- Prior approval: 2026-10-14 baseline for **up**, **down**, **help**, **shape intake** (retained where not superseded)
- Interview: operator decisions 2026-10-15 (attach subsumes TUI, interactive-only attach, markdown history v1)
- Help taxonomy: operator session [758da1e2-b417-48a1-9815-d1ad326834a2](758da1e2-b417-48a1-9815-d1ad326834a2) (listed/unlisted breakdown)
- Git comparison notes: [organized-cli.md](../organized-cli.md)
- Related: [foundry-up/spec.md](../foundry-up/spec.md) (idempotent `up`, preflight, foreground teardown) — this spec **refines human `up` copy** and adds **`down`**, **help**, **`shape`** intake, and **interactive attach**

## Operator outcome

After **`foundry up`**, the operator sees **“Foundry is ready”** (or a clear not-ready verdict) and knows what to run next without parsing `ok=True` lines. **`foundry down`** mirrors **`up`** and stops the same local stack. **`foundry -h`** and **`foundry help`** read like a short curriculum (setup → local stack → runs → gates → recovery).

**`foundry attach`** is the **only** interactive “work on a run” surface: optional run id, run list when omitted, **markdown-formatted scrollable history**, and **in-place answers and gate actions**. **`foundry shape`** hands off with **`foundry attach <id>`** (not a JSON stream). Scripts use **`foundry ledger …`**, not **`attach`**.

## Problem statement

Human CLI output still exposed internal readiness dimensions and implied **`down`** without providing it. Top-level help was complete but flat. **`foundry shape`** blocked through judgment yet exited without questions, mixing synchronous wait with batch-job disconnect.

Operators were sent to **`attach`** to “watch the run,” but **`attach`** streamed raw ledger JSON while **`tui`** held a richer UI—two metaphors, neither complete. The desired experience is **one attach plane**: pick a run, read steward history as markdown, act on the current wait, navigate back to the list—**collapsed per-node timeline** later; **v1 is full scrollable markdown history**.

## Scope

### In scope

1. **Human `foundry up` (delta on foundry-up)** — verdict-first stdout; `--json` unchanged; `-v` / `--verbose` for dimension detail.
2. **`foundry down`** — stop everything **`foundry up`** starts for the workspace; idempotent; human + `--json`.
3. **Grouped help** — workflow sections on default `-h`; **`foundry help`** index; **`foundry help -a`** for unlisted commands; **nested** subcommand `-h` shows real argparse help (not curriculum-only).
4. **Listed command set** — operator-facing commands in default help (see Decisions).
5. **`foundry shape` intake handoff** — default: complete **`shape.intake`** only, detach, run continues; **`--attach`**: intake lines then **interactive attach** to the new run.
6. **Intake validation errors** — insufficient input file and/or **`--prompt`** content → actionable human error (and structured `--json`).
7. **Interactive `foundry attach` (replaces TUI product role)**
   - Optional **`run`** positional; run **list** when omitted.
   - **Run view** with **rendered markdown** transcript (full history v1), **scrollable**.
   - **Wait actions** in run view (clarifying answers, gate decisions, execute start, advance where applicable)—host-backed when host is running.
   - **Navigation:** keybinding/command **back** from run view to run list; **Enter** and **pointer** open a run from the list.
   - Live updates while attached so new history appears without leaving attach.
8. **Non-interactive run inspection** — **`foundry ledger show`** (and **`ledger follow`** if required) as the **automation** path for JSON/events; migrate behavior from legacy **`attach --json`** / follow.
9. **`foundry tui`** — **deprecated**: alias to **`foundry attach`** with identical behavior, or remove after one release with migration message.

### Out of scope

- **Collapsed / expandable per-node timeline** in attach (v2); v1 may show node labels in markdown but not a navigator UI.
- Nested command trees (`foundry run …` as the only public API).
- Re-opening foundry-up idempotent reconcile, preflight matrix, or foreground Ctrl+C semantics (unchanged unless human copy touches the same formatter).
- Engine/steward changes to examine logic beyond what intake already enforces.
- Full IDE-parity chat (editing arbitrary files inside attach).
- **`foundry runs`** removal in v1 (may remain as one-shot CLI list; attach list is the interactive picker).
- `git help -g`-style concept guides (deferred).
- Windows headless subprocess policy (tracked in retro; separate implementation package unless bundled in map refresh).

## Decisions

| ID | Decision | Rationale | Retro link |
|----|----------|-----------|------------|
| D1 | Default **`shape`** stops after successful **`shape.intake`**; CLI detaches; run advances asynchronously on host | Intake ack + async run | § `shape` blocks… |
| D2 | **Interactive attach** is the watch/work surface; **`shape --attach`** opens it | Subsumes TUI intent | § attach console; interview |
| D3 | Intake failure → clear error (thin/missing input or prompt) | Fail fast at intake | § shape |
| D4 | **`foundry down`** mirrors **`foundry up`** scope (host + bridge this workspace reconciles) | Symmetric lifecycle | § `up` implies `down` |
| D5 | Human **`up`**: **“Foundry is ready”** / not-ready verdict + **Next:** + compact detail; dimensions on **`-v`/`--verbose`** only | Two audiences; reduces jargon | § telemetry vs verdict |
| D6 | Grouped **`-h`** + **`foundry help`** + **`foundry help -a`**; **leaf** parsers use real subcommand help | `runs`/`run` confusion | § workflow help; § runs vs run |
| D7 | **Listed** commands in default help; **`tui`** not listed (**attach** is the console) | Curriculum + power-user escape hatch | Interview |
| D8 | Post-intake stdout includes **`run=`**, **`foundry attach <id>`**, **`foundry status`** | Next steps without runbook | § shape Next |
| D9 | **`attach` = interactive only** | Clear operator metaphor | Interview Q2 |
| D10 | **Automation** = **`ledger show`** / **`ledger follow`** (or equivalent) | Scripts don’t use attach | Interview Q2 |
| D11 | **v1 attach history** = full scrollable **rendered markdown** transcript | Operator priority | Interview Q3 |
| D12 | **`attach`** optional run + **list ↔ run** navigation in one session | Picker in attach | Interview |

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

- **`shape.intake`** is the engine node that validates “enough information” in input file and prompt; AC refer to intake success/failure, not ad-hoc CLI checks.
- Host (or equivalent) **continues advancing** the run after CLI detach without requiring another **`run advance`** from the operator for the default happy path.
- Textual is a **required** dependency for interactive **`foundry attach`**.
- **Markdown transcript** is assembled from host **`run.context`** (markdown) over revisions and/or ledger-linked presentation events; exact composition is implementation detail but **must** read as continuous scrollable history in v1.
- **`answer` / `decide` / `start`** may remain as CLI commands for scripting; attach **may** call the same host RPCs internally.
- foundry-up **§1** readiness JSON shape remains; only **human** `_format_up` copy changes.
- **`down`** when already stopped: exit **0** with a short human confirmation (idempotent), matching **`up`** reconcile tone.
- Interactive **`attach`** requires a TTY; non-TTY exits with pointer to **`ledger`** commands.

## Acceptance criteria

### `foundry up` (human)

1. When all readiness dimensions pass, human stdout **starts with** a verdict equivalent to **“Foundry is ready”** (not `ready=True` as the lead).
2. Human stdout includes a **Next:** line (e.g. suggest **`foundry shape`** when appropriate).
3. Human stdout includes **compact** operational detail (e.g. judgment bridge URL, host PID) **without** per-dimension `ok=True` lines in the default view.
4. **`foundry up -v`** or **`--verbose`** prints the dimension breakdown (today’s-style detail is acceptable under verbose).
5. When not ready, human stdout states **not ready**, names what failed in operator language, and suggests the **next command** (e.g. **`foundry up`** again, fix adapter, start bridge).
6. **`foundry up --json`** output is **unchanged** in structure from foundry-up contract (human-only delta).

### `foundry down`

7. **`foundry down`** exists at top level and stops **the same components** **`foundry up`** starts/reconciles for the current workspace.
8. **`foundry down`** is **idempotent**: second invocation exits **0** with a clear “already stopped” or equivalent message.
9. Human and **`--json`** success envelopes are consistent with other porcelain commands (no error-shaped success).

### Help

10. **`foundry`** and **`foundry -h`** show **section headers** and **only listed** subcommands in journey order (table above), with one-line descriptions.
11. **`foundry help`** shows the same curated index; **`foundry help <command>`** works for listed commands (and documents unlisted ones when requested).
12. **`foundry help -a`** lists **all** top-level subcommands (listed + unlisted), analogous to **`git help -a`**.
13. Positional argparse help for individual subcommands (e.g. **`foundry shape -h`**, **`foundry run advance -h`**) shows **that command’s** flags and subcommands; root curriculum epilog does not replace nested help.

### `foundry shape` — default (no `--attach`)

14. On success, human output confirms **shape request received** and **intake successful** (operator-facing wording; may reference “intake” by name).
15. CLI **exits without blocking** through **`shape.examine`** or judgment.
16. Human output includes **`run=<id>`**, a line suggesting **`foundry attach <id>`**, and a line suggesting **`foundry status <id>`** (or **`foundry status`** when that resolves the new run).
17. The run **continues** to subsequent nodes (e.g. examine) without the operator running **`run advance`** for the default happy path.
18. **`foundry shape --json`** includes run id and intake outcome fields needed for automation.

### `foundry shape` — intake failure

19. When input file and/or **`--prompt`** lack sufficient information for intake, CLI exits **non-zero** with a **specific** human message (what was missing or rejected).
20. **`--json`** failure envelope includes structured reason/code suitable for scripts.

### `foundry shape --attach`

21. Prints the same **intake received / intake success** lines as default **`shape`**.
22. **Launches interactive attach** to the new run (same UI as **`foundry attach <id>`**).
23. Operator can leave attach UI; run continues; **`foundry attach <id>`** reopens run view with updated history.
24. When the run parks on **`user_input`**, **question text appears in the markdown/history pane** and **answer controls** are available in run view.

### `foundry attach` (interactive)

25. **`foundry attach`** with **no** run argument opens **run list** (run id, status, node, wait, revision or equivalent).
26. **`foundry attach <run_id>`** opens **run view** for that run without showing the list first.
27. From the list, **Enter** and **primary pointer activation** open run view.
28. Run view shows a **scrollable** region of **markdown-rendered** steward/history content covering **full run history to date** in v1 (updates as the run progresses).
29. Run view exposes **actions for the current wait** (at minimum: clarifying questions → submit answers; gate options → decide; execute start when applicable).
30. A **documented keybinding or command** returns from run view to **run list** without exiting the process.
31. **`foundry attach`** when stdout is **not** a TTY exits non-zero with a message naming **`foundry ledger show`** / **`ledger follow`** (or implemented automation equivalent).
32. **`foundry tui`** if retained prints a deprecation notice and runs **`foundry attach`** (or is removed).

### Non-interactive inspection

33. **`foundry ledger show`** (and **`ledger follow`** if added) supports **`--json`** and streaming use cases previously documented for legacy **`attach`**.
34. Operator runbook and **`shape`** hints do **not** tell scripts to use **`attach`**.

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
When the operator selects a run from the list
Then they see markdown-formatted scrollable history and current wait actions

Given foundry attach <run_id>
When the operator uses back navigation
Then they see the run list again without restarting foundry

Given foundry down after foundry up
When the operator runs foundry down
Then host and bridge started by up for this workspace are stopped
```

## Verification plan

- Headless Textual tests: list mount, open run via Enter and pointer, back navigation.
- Fixture run: markdown pane contains known presentation strings; **`user_input`** shows questions and submit path.
- **`attach`** on non-TTY → error + pointer to ledger command.
- CLI integration tests: human stdout for **`up`** (ready / not ready / verbose); **`down`** (stop + idempotent); **`foundry -h`** / **`help`** / **`help -a`** content (listed vs unlisted); nested **`run advance -h`** lists advance flags.
- **`shape`**: mock or fixture run where intake completes quickly — assert no long block, run id + attach hint; intake failure cases; **`--attach`** opens interactive UI (fixture).
- Regression: **`foundry up --json`** snapshot tests from foundry-up suite still pass.
- Manual: dogfood path — `up` → `shape` → `attach` without runbook.

## Implementation hints (optional)

- Evolve [tui/app.py](../../.cursor/foundry/cli/foundry_cli/tui/app.py) into interactive attach: markdown rendering, history buffer, list ↔ run stack; entry from **`cmd_attach`**.
- **`cmd_tui`**: delegate to **`cmd_attach`**.
- Move legacy JSON stream from **`stream_run_attach`** to **`ledger follow`** (or extend **`ledger show`**); update **`shape --attach`** to launch UI.
- **`parser.py`**: **`attach` run** `nargs='?'`; register **`down`**, **`help`**; fix **`format_help`** on nested parsers ([`help_catalog.py`](../../.cursor/foundry/cli/foundry_cli/help_catalog.py)).
- **`cmd_shape`**: stop condition at **`shape.intake`** completion; host auto-advance for subsequent nodes.
- **`_format_up`**, **`cmd_down`**: porcelain formatters.
- **`cli_docgen`**: sync with listed-command metadata.

## Deferred / follow-up

- **Node-collapsed timeline** navigator in attach.
- Concept guides (`foundry help <concept>`) like **`git help -g`**.
- **`shape`** positional file/text (retro GWT).
- Progress UI beyond markdown history (phase labels, spinners).
- Windows headless subprocess policy for **`taskkill`** and engine hooks (retro).
