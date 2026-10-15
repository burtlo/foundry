# CLI operator UX — porcelain lifecycle, help curriculum, shape intake handoff

Status: **draft specification** — from operator retro interview (2026-10-14).

## Source

- Bundle: [README](README.md)
- Retro: [retro.md](retro.md) — investigations: `up` human output, `down` symmetry, grouped help, `shape` blocking/handoff
- Help taxonomy: operator session [758da1e2-b417-48a1-9815-d1ad326834a2](758da1e2-b417-48a1-9815-d1ad326834a2) (listed/unlisted breakdown)
- Git comparison notes: [organized-cli.md](../organized-cli.md)
- Related: [foundry-up/spec.md](../foundry-up/spec.md) (idempotent `up`, preflight, foreground teardown) — this spec **refines human `up` copy** and adds **`down`**, **help**, and **`shape`** intake/async behavior

## Operator outcome

After **`foundry up`**, the operator sees **“Foundry is ready”** (or a clear not-ready verdict) and knows what to run next without parsing `ok=True` lines. **`foundry down`** mirrors **`up`** and stops the same local stack. **`foundry -h`** and **`foundry help`** read like a short curriculum (setup → local stack → runs → gates → recovery). **`foundry shape`** acknowledges **intake**, returns immediately with a **run id** and **attach/status** hints while the run continues; optional **`--attach`** streams examine progress through questions. Intake validation failures are explicit errors, not silent long blocks.

## Problem statement

Human CLI output still exposes internal readiness dimensions and implies **`down`** without providing it. Top-level help is complete but flat. **`foundry shape`** blocks through judgment yet exits without questions, mixing synchronous wait with batch-job disconnect. Operators need a clear **sync boundary** at **intake** and a first-class **watch** path via **`attach`**.

## Scope

### In scope

1. **Human `foundry up` (delta on foundry-up)** — verdict-first stdout; `--json` unchanged; `-v` / `--verbose` for dimension detail.
2. **`foundry down`** — stop everything **`foundry up`** starts for the workspace; idempotent; human + `--json`.
3. **Grouped help** — workflow sections on default `-h`; **`foundry help`** index; **`foundry help -a`** for unlisted commands; **`foundry help <command>`** where useful.
4. **Listed command set** — only operator-facing commands in default help (see Decisions).
5. **`foundry shape` intake handoff** — default: complete **`shape.intake`** only, detach, run continues; **`--attach`**: intake lines then attach-style streaming through examine including questions at `user_input`.
6. **Intake validation errors** — insufficient input file and/or **`--prompt`** content → actionable human error (and structured `--json`).

### Out of scope

- Nested command trees (`foundry run …` as the only public API).
- Replacing **`attach`** with **`tui`** in operator docs (**`tui` stays unlisted**).
- Re-opening foundry-up idempotent reconcile, preflight matrix, or foreground Ctrl+C semantics (unchanged unless human copy touches the same formatter).
- Engine/steward changes to examine logic beyond what intake already enforces.
- `git help -g`-style concept guides (deferred).

## Decisions

| ID | Decision | Rationale | Retro link |
|----|----------|-----------|------------|
| D1 | Default **`shape`** stops after successful **`shape.intake`**; CLI detaches; run advances asynchronously on host | Operator wants intake ack + async run, not block-until-questions | § `shape` blocks… |
| D2 | **`shape --attach`** = intake messages + same streaming as **`foundry attach`** until operator detaches; re-attach supported | Single “watch” metaphor; attach over TUI | Operator interview; § `shape` |
| D3 | Intake failure → clear error (thin/missing input or prompt) | Fail fast at intake, not after silent examine wait | Operator interview |
| D4 | **`foundry down`** mirrors **`foundry up`** scope (host + bridge this workspace reconciles) | Symmetric lifecycle | § `up` implies `down` |
| D5 | Human **`up`**: **“Foundry is ready”** / not-ready verdict + **Next:** + compact detail; dimensions on **`-v`/`--verbose`** only | Two audiences; reduces jargon | § telemetry vs verdict |
| D6 | Grouped **`-h`** + **`foundry help`** + **`foundry help -a`** for full list | Git-like discovery without breaking subcommand `-h` | § workflow-ordered help |
| D7 | **Listed** commands only in default help; **`host`**, **`run`**, **`tui`**, engine/maintainer commands **unlisted** | Curriculum + power-user escape hatch | Session 758da1e2 |
| D8 | Post-intake stdout includes **`run=`**, **`foundry attach <id>`**, **`foundry status <id>`** (or unambiguous **`status`**) | Next steps without runbook | Operator interview |

### Listed commands (default help)

| Section | Commands |
|---------|----------|
| Set up the workspace | `config`, `app` |
| Local Foundry | `up`, `down` |
| Start and watch runs | `shape`, `runs`, `status`, `attach` |
| When the run needs you | `answer`, `decide`, `start` |
| Recover or stop a run | `retry`, `cancel` |

**Unlisted (still callable):** `run`, `visit`, `gate`, `artifact`, `receipt`, `ledger`, `host`, `bridge`, `tui`, `cli`, `catalog`, `doc`, `dev` — visible via **`foundry help -a`** (and argparse on each command).

## Assumptions

- **`shape.intake`** is the engine node that validates “enough information” in input file and prompt; AC refer to intake success/failure, not ad-hoc CLI checks.
- Host (or equivalent) **continues advancing** the run after CLI detach without requiring another **`run advance`** from the operator for the default happy path.
- **`foundry attach`** streaming behavior is sufficient for progress during **`shape.examine`**; `--attach` may share implementation with **`cmd_attach`**.
- foundry-up **§1** readiness JSON shape remains; only **human** `_format_up` copy changes.
- **`down`** when already stopped: exit **0** with a short human confirmation (idempotent), matching **`up`** reconcile tone.

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
13. Positional argparse help for individual subcommands (e.g. **`foundry shape -h`**) remains available and accurate.

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
22. Then connects to **streaming** output: examine start, in-progress indication, eventual judgment output, and **clarifying questions** when the run reaches **`user_input`**.
23. Operator can **detach** (interrupt) without cancelling the run; **`foundry attach <id>`** resumes streaming from then.
24. Streaming UX is **aligned with `foundry attach`** (not a separate TUI-only path).

### Given / When / Then (smoke)

```gherkin
Given a workspace where foundry up reports ready
When the operator runs foundry shape --input-file <valid>
Then within a few seconds the CLI exits 0
And stdout contains intake success and run=<id>
And stdout mentions foundry attach and foundry status
And the run later reaches examine without the operator running shape again

Given foundry shape --attach with valid input
When examine runs and parks on user_input
Then the operator sees question text in the attach stream before detach

Given foundry down after foundry up
When the operator runs foundry down
Then host and bridge started by up for this workspace are stopped
```

## Verification plan

- CLI integration tests: human stdout for **`up`** (ready / not ready / verbose); **`down`** (stop + idempotent); **`foundry -h`** / **`help`** / **`help -a`** content (listed vs unlisted).
- **`shape`**: mock or fixture run where intake completes quickly — assert no long block, run id + hints; intake failure cases; **`--attach`** streams until `user_input` (fixture ledger).
- Regression: **`foundry up --json`** snapshot tests from foundry-up suite still pass.
- Manual: dogfood path from retro — `up` → `shape` → `attach` / `status` without runbook.

## Implementation hints (optional)

- **`cmd_shape`**: advance budget or stop condition at **`shape.intake`** completion; host auto-advance for subsequent nodes.
- **`_format_up`**, new **`cmd_down`** / **`_format_down`**: porcelain formatters.
- **`parser.py`**: register **`down`**, **`help`** subcommand or handler, custom **`format_help`** / epilog driven from **listed-command metadata** (avoid drift when adding subcommands).
- **`cli_docgen`**: either generate help groups from same metadata or document manual sync requirement in implementation map.
- Reuse **`cmd_attach`** / ledger follow for **`shape --attach`**.

## Deferred / follow-up

- Concept guides (`foundry help <concept>`) like **`git help -g`**.
- Promote selective unlisted commands if operators routinely need **`run context`** without **`attach`**.
- Progress UI beyond ledger streaming (spinner, phase labels) if attach stream is too sparse.
