# Operator experience — readiness output, shutdown, and help layout

Status: **open design investigation**. The operator dogfooded the Foundry registry workspace (`~/src/foundry`) after `foundry up` shipped. Observations below are from the operator’s account and a code snapshot of the CLI; they are not a run evaluation.

**Run evidence:** No `.foundry/runs/{run_id}` was supplied for this session. evaluate-run not run—engine verdict omitted.

Maintained operations: [operator-runbook.md](../../operator-runbook.md). Feature context for `foundry up`: [foundry-up/spec.md](../foundry-up/spec.md).

## Purpose and setting

The operator wanted a quick, trustworthy answer to “is Foundry running and healthy in this workspace?” after `foundry up`, plus a mental model for turning local services off. They also compared top-level `foundry` help to `git` and asked for flow-oriented grouping so commands are easier to find at the right moment in a workflow.

## Experience in the operator's terms

`foundry up` returned accurate readiness facts in a line-oriented `key=value` style. The operator could see bridge URL, host PID, and health RPC success, but had to translate internal names (`bridge`, `adapter`, `ready`, repeated `ok=True`) into “I can run `shape` now.” Running `up` created a strong expectation that `foundry down` exists; discovering shutdown meant reading the runbook or inferring from `host` subcommands. Running bare `foundry` listed every subcommand alphabetically in argparse order, which is complete but not ordered by the operator journey (bootstrap → local services → shape a run → attend gates → inspect).

On Windows (2026-10-15), after `foundry up` the operator saw brief command windows flash and disappear while using the CLI; the cause was not obvious (subcommands vs background services). They opened `foundry tui`, saw a run list, clicked rows with no effect, and formed an expectation that this TUI is the surface for choosing a run to attach to—not a separate debug tool. `foundry runs --help` was read as help for the `run` command family, not as documentation for listing runs.

## Feedback investigations

### `foundry up` reads like service telemetry, not a readiness verdict

*Operator signal (paraphrased): It's accurate but could use more user-focused formatting — what do `ready=True` and `ok=True` mean; what is a bridge; is process vs health useful; what is the adapter?*

- **Expected:** A short human verdict (“Foundry is ready for judgment in this workspace”) with optional detail, not a dump of dimension flags.
- **Observed:** Human output from the operator’s terminal (paraphrased structure):

  ```
  workspace=/Users/lynnfrank/src/foundry ready=True
  bridge ok=True url=http://127.0.0.1:8791/v1/agent
  host process ok=True pid=20010
  host health ok=True detail=health RPC ok
  adapter ok=True configured=True reachable=True
  ```

  Source: operator account. Implementation: [`_format_up`](../../../.cursor/foundry/cli/foundry.py) prints flat key=value lines; JSON envelope carries the same structure from [`cmd_up`](../../../.cursor/foundry/cli/foundry_cli/up_commands.py) and [`_readiness_payload`](../../../.cursor/foundry/cli/foundry_cli/up_commands.py). `ready` is true only when bridge, host process, host health, and adapter dimensions all pass [`_all_ready`](../../../.cursor/foundry/cli/foundry_cli/up_commands.py).
- **Friction cost:** Extra cognitive load on every up; operators may ignore useful lines or distrust jargon they do not need for day-to-day work.
- **Touchpoints:** Readiness dimensions in [`readiness/dimensions.py`](../../../.cursor/foundry/cli/foundry_cli/readiness/dimensions.py); docs in [cli/up.md](../../cli/up.md) and [operator-runbook.md](../../operator-runbook.md) (lists dimensions but does not define operator-facing names). Concepts: [agent-adapter.md](../../concepts/agent-adapter.md), [judgment-bridge feature](../../features/judgment-bridge.md).
- **Interpretation:** The product correctly separates **process** (PID alive), **health** (host RPC), **bridge** (HTTP judgment endpoint health), and **adapter** (host configured to reach that URL). The formatter exposes the internal decomposition by default instead of leading with outcome and “what you can do next” (`foundry shape`, `foundry host status`, `foundry host logs`).
- **Options and tradeoffs:**
  - **Narrative summary + collapsible detail:** Lead with one line (ready / not ready + next step); indent or `--verbose` for dimensions. Low maintenance if copy is centralized; power users may still want `--json` only.
  - **Rename in human output only:** e.g. “Judgment bridge” instead of `bridge`, “Host” merged line when process+health agree. Cheaper than redesign but still does not answer “what now?”
  - **Single “readiness” score with reasons:** Like preflight messages in [`readiness/preflight.py`](../../../.cursor/foundry/cli/foundry_cli/readiness/preflight.py). Reuses existing hints; risk of hiding PID/URL needed for debugging.
- **Probe:** Show three operators the same JSON payload rendered as (A) current lines, (B) one-line verdict + “Details:” block, (C) verdict + only failures. Measure time-to-correct answer: “Can I run `shape`?” and “What broke?”
- **Status:** open

### `foundry up` implies `foundry down`, but shutdown is fragmented

*Operator signal: "Running `foundry up` makes me think that there should be a `foundry down`." / "What's the command for shutting things down? I think it should be `foundry down`."*

- **Expected:** Symmetric lifecycle: one command to start/reconcile local Foundry services, one command to stop them for the workspace.
- **Observed:** No `down` subcommand in [`parser.py`](../../../.cursor/foundry/cli/foundry_cli/parser.py). [operator-runbook.md](../../operator-runbook.md) documents **Stop with `foundry host stop`** for manual debug; bridge stop is not exposed as `foundry bridge stop` (only `bridge start` in parser). [`stop_bridge`](../../../.cursor/foundry/cli/foundry_cli/bridge/lifecycle.py) exists and is used from [`cmd_up` foreground teardown](../../../.cursor/foundry/cli/foundry_cli/up_commands.py) and reconcile paths. Operator note captured in [foundry_up-now_down.md](../foundry_up-now_down.md).
- **Friction cost:** Discoverability gap after a successful `up`; risk of leaving bridge running while believing “Foundry is down”; mismatch between product metaphor (`up`) and documented shutdown (`host stop` only).
- **Touchpoints:** [`cmd_host_stop`](../../../.cursor/foundry/cli/foundry_cli/host_commands.py); bridge lifecycle [`stop_bridge`](../../../.cursor/foundry/cli/foundry_cli/bridge/lifecycle.py); foreground Ctrl+C path in `cmd_up` (stops children started by that invocation only).
- **Interpretation:** `up` is positioned as the porcelain entrypoint while stop remains split across host RPC, bridge lifecycle (internal), and foreground-only bridge teardown. The operator’s mental model (compose up / compose down) is predictable; the CLI currently implements only half of that pair at the top level.
- **Options and tradeoffs:**
  - **`foundry down`:** Stop host then bridge for workspace (mirror `up` scope). Clear pairing; must define behavior when bridge is shared or was started outside `up`, and idempotency when already stopped.
  - **Document alias only:** Runbook section “Shutting down” with `host stop` + future `bridge stop`. No new code; leaves asymmetry.
  - **`foundry up --foreground` as the “session” stop:** Already stops children on Ctrl+C per spec D10; does not help default detached `up`, which is the common path.
- **Probe:** In a short operator test, after `foundry up`, ask how to stop everything without reading docs. Record commands tried and whether bridge process remains. Compare with a prototype `foundry down` help string only (no implementation) for expectation fit.
- **Status:** open (operator request to add `foundry down` recorded in [foundry_up-now_down.md](../foundry_up-now_down.md); not implemented in CLI at time of writing)

### Top-level help is complete but not workflow-ordered

*Operator signal (paraphrased): Git groups commands by operation with short descriptions; Foundry’s list is close but flow order and grouping would make it clearer when to run things.*

- **Expected:** Help organized by operator journey (setup → run local stack → start/observe runs → gate actions → advanced/engineering), similar to `git`’s categorized listing.
- **Observed:** Standard argparse subparser list in [`build_parser`](../../../.cursor/foundry/cli/foundry_cli/parser.py) — alphabetical / definition order, one line per subcommand. Operator pasted comparison in [organized-cli.md](../organized-cli.md). No custom `format_help` or epilog in the CLI tree at time of review.
- **Friction cost:** Harder to onboard; high-value commands (`up`, `shape`, `status`, `decide`) sit in a flat namespace with catalog/doc/dev tooling.
- **Touchpoints:** Parser registration in [`parser.py`](../../../.cursor/foundry/cli/foundry_cli/parser.py); command routing in [`foundry.py`](../../../.cursor/foundry/cli/foundry.py); generated docs via [`cli_docgen.py`](../../../.cursor/foundry/cli/foundry_cli/cli_docgen.py) (may need to stay consistent if help is hand-authored).
- **Interpretation:** Argparse defaults optimize for completeness, not curriculum. Foundry’s command count crossed the threshold where grouping becomes a primary navigation aid (the operator explicitly used `git` as the reference).
- **Options and tradeoffs:**
  - **Custom help epilog** (static groups, fixed order): Fast to ship; must be updated when subcommands change unless generated from metadata.
  - **Subgroup commands** (`foundry run …`, `foundry workspace …`): Strong structure; breaking change for scripts and muscle memory.
  - **`foundry help` / `foundry help shape`:** Git-like; keeps argparse for `-h` on subcommands but adds a curated index command.
- **Probe:** Card-sort subcommands with two operators into “first day”, “during a run”, “break/fix”, “maintainer”; compare resulting groups to a draft epilog. Track mismatches as the taxonomy test.
- **Status:** open

### `foundry shape` blocks on judgment, then exits before showing questions

*Operator signal (paraphrased): I run `shape` and it blocks for a while — I thought this was async. I expected either fire-and-forget or stay connected until questions appear so I can answer. Instead it's the worst of both worlds.*

- **Expected:** (A) submit the shape request and return immediately while examination runs in the background, or (B) one interactive session that shows progress, surfaces clarifying questions, and accepts answers.
- **Observed:** Operator ran `foundry shape --input-file docs/plans/organized-cli.md`; after a long silent period the CLI printed `run=foundry-0004 node=shape.examine revision=4 wait=user_input summary='2 clarifying question(s) need answers'` and exited. Source: operator account. [operator-runbook.md](../../operator-runbook.md) documents that `shape` advances until a wait and that answers use separate `foundry answer` + optional `run advance` steps.
- **Friction cost:** Minutes of opaque blocking; questions not visible in the success line; forces a second discovery path (`status --json`, `run context --markdown`, `attach`, or `foundry tui`) before the operator can continue.
- **Touchpoints:**
  - [`cmd_shape`](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) — create run, then [`_advance_via_host_or_local`](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) with default `step_budget=8`.
  - [`advance_run_durable`](../../../.cursor/foundry/cli/foundry_cli/run_service.py) — while `wait.kind == "agent"`, synchronously [`dispatch_for_agent_wait`](../../../.cursor/foundry/cli/foundry_cli/engine/agent/dispatch.py) → `adapter.invoke()` (HTTP to judgment bridge / Cursor SDK).
  - Host path: same `run.advance` RPC with extended client timeout per [`timeout_policy.py`](../../../.cursor/foundry/cli/foundry_cli/host/timeout_policy.py) (runbook § long advance).
  - Human formatter [`_format_shape`](../../../.cursor/foundry/cli/foundry.py) — run id, node, revision, wait kind + summary only (no question text).
  - Contrast: [`cmd_attach`](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) streams ledger events until Ctrl+C; TUI shows `user_input` fields ([runbook](../../operator-runbook.md)).
  - Architecture intent: [job-host-architecture.md](../../concepts/job-host-architecture.md) — “A CLI invocation may exit while a run continues”; `wait.kind=agent` vs `user_input` table.
- **Interpretation:** The engine/host model is **durable and resumable** (async at the run level), but **`foundry shape` is implemented as a synchronous “advance until parked” RPC** that **includes inline agent dispatch**. That matches “get me to the first human boundary in one command” but contradicts an intuitive reading of “async framework” and leaves a gap between parking on `user_input` and presenting the questions. The operator correctly names a UX cliff: block like a synchronous API, disconnect like a batch job, omit the payload needed for the next step.
- **Options and tradeoffs:**
  - **`shape --no-advance` / `shape --wait-at create`:** Return run id immediately; operator runs `run advance` or relies on auto-advance. True async CLI; more commands and easier to start runs without bridge.
  - **Advance stops at `agent` wait; host or daemon dispatches:** CLI returns fast with `wait=agent`; judgment runs off the critical path. Requires reliable background dispatch and progress events (attach/TUI become first-class).
  - **`shape --follow`:** Block with staged stderr (“dispatching shape.examine…”) then print questions from context packet or structured wait payload before exit. Keeps one command for many users; still blocks through judgment unless combined with split dispatch.
  - **Interactive REPL mode:** After create, loop: advance slice → render questions → read answers → `answer` RPC. Best for (B); more CLI complexity.
  - **Improve parking output only:** On `user_input`, print question ids/text and suggested `foundry answer` line (cheap; does not fix silent judgment wait).
- **Probe:** Time-to-first-feedback for `shape` with and without stderr progress lines; measure how many operators find questions without reading runbook. A/B: exit with embedded questions vs current summary-only line.
- **Status:** open

**What to do today (runbook):** After `shape` parks on `user_input`, use `foundry run context --run foundry-0004 --markdown` (or `foundry tui`) to read questions, then `foundry answer foundry-0004 --answers '{...}'` and `foundry run advance --run foundry-0004` if needed. Use `foundry attach foundry-0004` during long advances to see ledger activity.

### `foundry up` should name the workspace in the readiness verdict

*Operator signal: When I run `foundry up` I expect `Foundry is ready for workspace: C:\Users\lynnv\src\foundry` with host pid and bridge URL, then a **Next:** block that suggests `foundry shape PLANFILE.md`.*

- **Expected:** Verdict includes the resolved workspace path (especially on Windows); **Next:** is a labeled block with a concrete shape example, not only the bare subcommand name.
- **Observed:** Porcelain formatter prints `Foundry is ready`, then `Next: foundry shape`, then `workspace: …`, `bridge: …`, `host pid: …` ([`format_up_human`](../../../.cursor/foundry/cli/foundry_cli/readiness/formatting.py)). Order differs from the operator sketch (verdict before **Next:**, workspace on its own line not in the headline). GWT captured in [foundry-up.md](../foundry-up.md) and [foundry-up/gwt-scenario.md](../foundry-up/gwt-scenario.md). Source: operator account (2026-10-15).
- **Friction cost:** On multi-workspace machines, “ready” without the path in the headline forces a second read of `workspace:`; generic **Next:** does not reinforce the file-or-text shape habit the operator wants.
- **Touchpoints:** [`format_up_human`](../../../.cursor/foundry/cli/foundry_cli/readiness/formatting.py); approved copy targets in [cli-operator-ux/spec.md](spec.md) § `foundry up` (verdict + **Next:** + compact detail, no `ok=True` in default view).
- **Interpretation:** Implementation is close to D5 in the spec but omits workspace-in-headline and a structured **Next:** section; the operator is specifying acceptance examples, not asking for more telemetry.
- **Options and tradeoffs:**
  - **Headline + labeled Next block:** `Foundry is ready for workspace: {path}`; blank line; detail lines; `Next:` with indented examples. Matches GWT; long paths may wrap on narrow terminals.
  - **Keep current order, add workspace to headline only:** Minimal diff; **Next:** still generic unless templated from last shaped file (heuristic, often wrong).
  - **Config-driven Next hint** (e.g. default plan path in `.foundry/app.yaml`): Personalized **Next:** at cost of manifest surface and stale defaults.
- **Probe:** Show three operators the current output vs GWT on Windows and macOS paths; measure correct answers to “which workspace?” and “what do I run next?”
- **Status:** open (partially mitigated—human porcelain exists; GWT deltas remain)

### `foundry shape` should accept a positional file or quoted idea

*Operator signal: `foundry shape PLANFILE.md` and `foundry shape "an idea to shape"` should start the same workflow as `--input-file` and `--input`.*

- **Expected:** One positional argument: path to a plan file, or quoted text when not a path—mirroring common CLI ergonomics (`git commit -m` vs editor file).
- **Observed:** [`build_parser`](../../../.cursor/foundry/cli/foundry_cli/parser.py) requires exactly one of `--input` / `--prompt` / `--input-file`; `_resolve_shape_input` never reads a positional ([`user_cli.py`](../../../.cursor/foundry/cli/foundry_cli/user_cli.py)). Omitting flags yields `INPUT_REQUIRED`. Source: operator account; code snapshot.
- **Friction cost:** Extra flags and help reading on every shape; disconnect between **Next:** examples (`foundry shape PLANFILE.md`) and what the parser accepts.
- **Touchpoints:** Parser group at `shape` in [`parser.py`](../../../.cursor/foundry/cli/foundry_cli/parser.py); `_resolve_shape_input`; tests in [`test_user_cli_shape.py`](../../../.cursor/foundry/cli/tests/unit/test_user_cli_shape.py).
- **Interpretation:** The product teaches file-first shaping in readiness **Next:** lines but only implements flag-based intake—a curriculum/implementation mismatch.
- **Options and tradeoffs:**
  - **Optional positional `request`:** If value is an existing file path, read file; else treat as inline text. Simple for operators; ambiguous when a single-line string is also a valid path.
  - **Positional with explicit disambiguation flag** (`--as-text`): Safer; more flags.
  - **Document-only alias** in help examples without parser change: Zero code risk; frustration persists.
- **Probe:** Attempt `foundry shape docs/plans/foundry-up.md` in a dogfood session; record whether operators try positional before `-h`.
- **Status:** open

### Shape success output should read like “started run” plus a **Next:** block

*Operator signal: After shape with file or text I expect `Started run \`foundry-0006\` with shape request` and a **Next:** block with commented `attach` and `status` lines.*

- **Expected:** Past-tense acknowledgment of the run id, labeled **Next:** with suggested commands (comments optional in docs; porcelain may omit `#` commentary).
- **Observed:** [`_format_shape`](../../../.cursor/foundry/cli/foundry.py) prints intake lines when complete, then `run={id}`, then bare `foundry attach …` / `foundry status …` without a **Next:** header. JSON envelope includes `attach_hint` / `status_hint` ([`cmd_shape`](../../../.cursor/foundry/cli/foundry_cli/user_cli.py)). Spec D8 allows `run=` plus hints ([spec.md](spec.md)). Operator GWT: [foundry-up.md](../foundry-up.md). Source: operator account.
- **Friction cost:** Low if hints are present, but copy does not match the operator’s mental model of “started” + curriculum block; inconsistency with `foundry up` **Next:** styling.
- **Touchpoints:** [`_format_shape`](../../../.cursor/foundry/cli/foundry.py); [cli-operator-ux/spec.md](spec.md) AC 14–16 (intake messaging and hints).
- **Interpretation:** Spec and implementation optimized for machine-parseable hints; operator wants symmetric porcelain with `up` (verdict + **Next:**).
- **Options and tradeoffs:**
  - **Align `_format_shape` with GWT wording:** Shared helper with `format_up_human` for **Next:** blocks; update spec AC wording to match or document intentional deviation.
  - **Keep minimal `run=` line:** Less churn; GWT lives only in acceptance doc until orchestration picks copy.
- **Probe:** Card-sort current shape output vs GWT—do operators identify the run id and next command equally fast?
- **Status:** open (hints exist; GWT copy and **Next:** block do not)

### `foundry attach` should feel like a scrollable chat console, not a JSON tap

*Operator signal: I want markdown rendered well, a viewport I can move around, and something that approximates Cursor-style chat—not a dump of ledger events.*

- **Expected:** Interactive console: formatted markdown (plans, questions, presentation), scrollable history, optional summary of other commands (`status`, `answer`, `decide`).
- **Observed:** [`cmd_attach`](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) calls [`stream_run_attach`](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) with `human_questions=False`—stdout is one JSON object per ledger event; header and wait summary on stderr. Clarifying questions print to stderr only when `human_questions=True` (used from `foundry shape --attach` in [`foundry.py`](../../../.cursor/foundry/cli/foundry.py), not from standalone attach). Steward markdown is available via **`foundry run context --markdown`** ([`render.py`](../../../.cursor/foundry/cli/foundry_cli/render.py)) and **`foundry tui`** ([`tui/app.py`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py)), which is intentionally unlisted in [spec.md](spec.md). Source: operator account; code snapshot.
- **Friction cost:** Operators who follow **Next: foundry attach** discover a debug stream, then must learn `run context`, `tui`, or IDE chat—high context switch, weak trust in “attach” as the watch surface.
- **Touchpoints:** Attach parser in [`parser.py`](../../../.cursor/foundry/cli/foundry_cli/parser.py); streaming loop in `stream_run_attach`; markdown rendering in [`render.py`](../../../.cursor/foundry/cli/foundry_cli/render.py); Textual TUI in [`tui/`](../../../.cursor/foundry/cli/foundry_cli/tui/).
- **Interpretation:** “Attach” names a product metaphor (stay connected to the run) but implements an event pipe. Rich rendering exists on adjacent commands, not on the command the shape handoff advertises.
- **Options and tradeoffs:**
  - **Upgrade attach default:** Poll snapshot + render context markdown on revision changes; use a pager (e.g. `less`) or terminal UI library for scrollback. Delivers GWT; must define behavior for large artifacts and Windows terminals.
  - **Promote `foundry tui` in Next hints instead of attach:** Reuses Textual; conflicts with D7 unlisted `tui` and requires Textual install.
  - **Hybrid:** Human attach shows latest rendered packet + optional `--json` / `--raw-events` for automation. Two modes; document clearly.
  - **External “console” subcommand** wrapping attach + context render:** Avoids breaking JSON attach for scripts; another name to learn.
- **Probe:** After shape, ask operators to “watch the run and read clarifying questions” using only `foundry attach`; record first successful path and time. Repeat with a prototype pager rendering `run context --markdown` on each revision bump.
- **Status:** open

### TUI run list ignores mouse click (Enter-only navigation)

*Operator signal: I run `foundry tui`, see runs, press on them, and nothing happens.*

- **Expected:** Selecting or clicking a row opens that run (same as choosing a run to attach to).
- **Observed:** At the time of this report, the run list rendered with copy “select a row and press Enter”; navigation was bound to Enter only, so a mouse click moved the cursor without opening [`RunDetailScreen`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py). Source: operator account and historical code snapshot. The current implementation now handles `DataTable.RowSelected` in [`RunListScreen._on_run_row_selected`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py), covered by [`test_run_list_row_selected_opens_run_detail`](../../../.cursor/foundry/cli/tests/unit/test_tui.py).
- **Friction cost:** Feels broken on first use; operators assume the list is interactive like other TUIs; retry clicks waste time before discovering the keyboard hint in the title line.
- **Touchpoints:** [`RunListScreen`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py); pointer and Enter coverage in [`test_tui.py`](../../../.cursor/foundry/cli/tests/unit/test_tui.py).
- **Interpretation:** The original TUI implemented keyboard-first patterns without wiring the primary pointer affordance. The later RowSelected repair confirms this was a local interaction gap rather than a host or run-state problem.
- **Options and tradeoffs:**
  - **Open on row select / double-click:** Matches operator expectation; risk accidental navigation on single-click if detail screen is heavy.
  - **Show footer hint “Enter to open” and highlight row on click only:** Keeps Enter as confirm; still requires a second action for pointer users.
  - **Default `foundry tui --run <id>` from shape handoff:** Skips list when run id is known; does not fix list UX for multi-run workspaces.
- **Probe:** Record success rate opening a run with mouse only vs keyboard in a five-run workspace; add a RowSelected handler in a branch and re-test.
- **Status:** fixed-in-code (row selection handler and headless pointer-path test present in the 2026-10-16 snapshot)

### TUI should be the run-picker / attach console, not a parallel tool

*Operator signal (paraphrased): The `tui` view should be what I see when I'm choosing to attach to a run.*

- **Expected:** After `shape` or `foundry up`, one full-screen console to pick among runs, read markdown context, answer questions, and stay connected—replacing the need to discover `attach` vs `run context` vs IDE chat.
- **Observed:** [`foundry tui`](../../../.cursor/foundry/cli/foundry_cli/tui_commands.py) launches a host-only Textual client with run list + detail ([`tui/app.py`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py)); [`foundry attach`](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) streams raw ledger JSON by default. Curriculum help lists `attach` under “Start and watch runs” but marks `tui` **unlisted** in [`help_catalog.py`](../../../.cursor/foundry/cli/foundry_cli/help_catalog.py). Related expectation already captured under attach console in this retro. Source: operator account (2026-10-15).
- **Friction cost:** Three surfaces (`attach`, `run context --markdown`, `tui`) compete for “watch the run”; shape **Next:** hints still point at attach, not the UI the operator imagines.
- **Touchpoints:** [cli-operator-ux/spec.md](spec.md) D7 (unlisted `tui`); [operator-runbook.md](../../operator-runbook.md); shape formatters in [`foundry.py`](../../../.cursor/foundry/cli/foundry.py).
- **Interpretation:** The product has the richer UI (`tui`) but teaches and lists the poorer one (`attach`); the operator is naming the desired primary operator console, not asking for a new feature category.
- **Options and tradeoffs:**
  - **Promote `tui` in curriculum and shape Next lines** (“`foundry tui` or `foundry tui --run <id>`”). Honest handoff; requires Textual dependency and Windows terminal support story.
  - **Merge attach human mode with TUI rendering** (single command name `attach`). One metaphor; large implementation shift.
  - **Rename/describe:** `foundry console` alias to `tui` with attach semantics in help copy. Extra surface unless attach is deprecated.
- **Probe:** After shape parks on `user_input`, ask operators to find questions using only help-listed commands vs allowing `tui`; measure time and command count.
- **Status:** open

### `foundry runs --help` vs `foundry run` — naming and help content collide

*Operator signal: When I run `foundry runs --help` I expect to see the help for the `run` command.*

- **Expected:** Either `runs` help documents listing runs, or the plural command is obviously tied to the `run` subcommand tree (`create`, `advance`, `context`, …).
- **Observed:** Parser defines **`runs`** as “List workspace runs” and a separate top-level **`run`** group for lifecycle/engine commands ([`parser.py`](../../../.cursor/foundry/cli/foundry_cli/parser.py)). `run` is **unlisted** in curriculum help ([`UNLISTED_TOP_LEVEL_COMMANDS`](../../../.cursor/foundry/cli/foundry_cli/help_catalog.py)). Every subparser uses [`_FoundryArgumentParser.format_help`](../../../.cursor/foundry/cli/foundry_cli/parser.py) → [`format_curriculum_help`](../../../.cursor/foundry/cli/foundry_cli/help_catalog.py), so `foundry runs --help` and `foundry run --help` both append the global journey sections and **do not** enumerate `run create` / `run advance` / `run context` children. Verified on Windows: `python foundry.py runs --help` shows `--local` plus curriculum; `foundry run --help` shows no subcommands. Docs for listing: [cli/runs.md](../../cli/runs.md). Source: operator account + CLI reproduction.
- **Friction cost:** Plural/singular pair looks like a typo or alias; advanced `run` tools stay hidden; `--help` on the wrong word reinforces confusion.
- **Touchpoints:** [`cmd_help`](../../../.cursor/foundry/cli/foundry_cli/help_commands.py) (per-command help still uses curriculum formatter on nested parsers); listed command `runs` vs unlisted `run`.
- **Interpretation:** Two independent naming choices (English plural for list vs noun namespace for engine RPCs) plus a help formatter optimized for root curriculum misfire for both discovery and the operator’s mental model.
- **Options and tradeoffs:**
  - **Context-sensitive `format_help`:** Root keeps curriculum; leaf parsers use stock argparse (subcommands + flags). Fixes `run --help` without losing grouped root `-h`.
  - **Rename list command** (`foundry run list` or `foundry status --all`). Clear hierarchy; breaking change for scripts using `runs`.
  - **Cross-link in `runs --help` epilog:** “For engine commands use `foundry run create` …” Cheap; does not fix missing subcommand listing on `run --help`.
  - **Alias `runs` → document only** that it is not `run`. Zero code; frustration persists.
- **Probe:** Ask operators what `foundry runs` does before running it; then show `run --help` output and ask where `run context` is documented.
- **Status:** open

### Stray console windows on Windows after `foundry up` and subcommands

*Operator signal (paraphrased): After `foundry up` I keep seeing command windows appear and disappear—it doesn't make sense whether that's subcommands or something else.*

- **Expected:** Local services start headlessly; routine CLI use does not spawn visible `cmd` flashes.
- **Observed:** Operator on **win32** reports repeated brief console windows during `foundry up` and ongoing CLI use. Code paths that spawn visible consoles on Windows (hypothesis unless traced on operator machine):
  - **Detached bridge/host** use [`detached_python_executable`](../../../.cursor/foundry/cli/foundry_cli/detached_spawn.py) (`pythonw.exe` when available) and [`CREATE_NO_WINDOW`](../../../.cursor/foundry/cli/foundry_cli/detached_spawn.py) in [`host_commands._spawn_detached`](../../../.cursor/foundry/cli/foundry_cli/host_commands.py) and [`bridge/lifecycle._spawn_detached_bridge`](../../../.cursor/foundry/cli/foundry_cli/bridge/lifecycle.py)—intended headless.
  - **`foundry up`** may call [`cmd_host_stop`](../../../.cursor/foundry/cli/foundry_cli/up_commands.py) when adapter config disagrees, then restart host; bridge reconcile may call [`stop_bridge`](../../../.cursor/foundry/cli/foundry_cli/bridge/lifecycle.py) → [`_terminate_pid`](../../../.cursor/foundry/cli/foundry_cli/bridge/lifecycle.py) → `subprocess.run(["taskkill", ...])` **without** `CREATE_NO_WINDOW` (verified in code).
  - **Run advance / execute** can invoke [`subprocess.run`](../../../.cursor/foundry/cli/foundry_cli/engine/hooks.py) and git helpers in [`execute_step_executor.py`](../../../.cursor/foundry/cli/foundry_cli/engine/execute_step_executor.py) without hidden-window kwargs—visible flash per hook if the default is a new console (platform-dependent).
  Source: operator account; mechanism partially code-backed, not reproduced in this capture session.
- **Friction cost:** Breaks trust (“is something crashing?”); distracting during focus; especially jarring after `up` advertised as one-shot bootstrap.
- **Touchpoints:** [`up_commands.cmd_up`](../../../.cursor/foundry/cli/foundry_cli/up_commands.py); bridge stop; [foundry-up/implementation.md](../foundry-up/implementation.md) win32 spawn notes; probe doc [foreground-up-teardown.md](../foundry-up/probes/foreground-up-teardown.md).
- **Interpretation:** Headless spawn was designed for long-lived children, but **stop/teardown and engine hooks** still use stock `subprocess.run`, which on Windows often allocates a transient console. Operators cannot tell flashes from bridge/host restarts vs per-subcommand git hooks.
- **Options and tradeoffs:**
  - **Centralize `run_hidden` helper** (CREATE_NO_WINDOW + startupinfo) for all CLI-spawned children including `taskkill`. Low scope; must validate taskkill still succeeds.
  - **Stop bridge via HTTP/control channel** instead of `taskkill`. No console; more design work.
  - **Surface “restarted host (adapter mismatch)” in `up` human output** so flashes correlate with action. Does not remove flash.
  - **Document Windows flashes as known** in runbook. Honest; poor UX.
- **Probe:** On win32, run `foundry up` with Process Monitor or screen recording; count `conhost.exe` / `cmd.exe` spawns and map to `taskkill`, `git`, or `python.exe`. Repeat after wrapping `taskkill` in hidden spawn kwargs.
- **Status:** open

## Attach dogfood follow-up — 2026-10-16

The operator used the newly interactive `foundry attach` surface, first on the running-run list and then on a `shape.examine` run parked for three clarifying answers. This follow-up is product feedback on information architecture, readability, and input ergonomics; no run path was supplied, so evaluate-run not run—engine verdict omitted.

### Run-list labels should describe operator meaning

*Operator signal (paraphrased): I can understand “decision” and “user input,” but the headers and values should be more human-friendly, with clearer names, spacing, and color.*

- **Expected:** A run picker that reads as an operator dashboard: “Run ID,” “Current step,” and “Needs” (or equivalent), with human phrases such as “Needs approval” and “Needs answers.”
- **Observed:** On the running-task list, the operator saw raw headers and values including `run_id`, `node`, `wait`, `decision`, and `user_input`. Source: operator account. [`RunListScreen.on_mount`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) defines the literal columns `run_id`, `status`, `node`, `wait`, `revision`; [`_apply_runs`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) inserts `active_node_id` and `wait_kind` without an operator-facing formatter. `zebra_stripes=True` is enabled, but there is no status/wait-specific color mapping.
- **Friction cost:** Internal vocabulary slows scanning and makes the most important distinction—“does this run need me?”—less visible than implementation fields.
- **Touchpoints:** [`tui/app.py`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) (`RunListScreen`); host fields are documented in [operator-runbook.md](../../operator-runbook.md#host-read-api-tui-and-integrations); current list contract is [spec.md](spec.md#foundry-attach-interactive) AC 25.
- **Interpretation:** The list is structurally complete but projects the host protocol directly into the UI. The operator’s wording suggests the `wait` column is not merely a label-cleanup problem: it should answer whether approval, answers, agent work, or no action is pending.
- **Options and tradeoffs:**
  - **Human formatter at the UI boundary:** `Run ID`, `Status`, `Current step`, `Needs`, `Version`; map `decision` → `Approval`, `user_input` → `Answers`, `agent` → `Agent`. Cheap and keeps RPC values stable; terminology must be maintained as wait kinds evolve.
  - **Action sentence instead of wait kind:** “Needs your approval,” “Needs your answers,” “Working,” “Ready to advance.” More immediately useful; longer strings need width and truncation rules.
  - **Color plus text:** Add restrained semantic styling for human action vs background work. Faster scanning; color must remain supplemental for accessibility and low-color terminals.
- **Probe:** Test the current table against both alternatives with mixed waits; ask operators which run needs them and what action it needs. Verify at narrow terminal widths and without color.
- **Status:** open

### The command palette is the right help model, but it is hidden

*Operator signal: “That's the help I like.”*

- **Expected:** An obvious in-product way to open a help/shortcut panel that explains arrows, Enter/click, Tab, back, refresh, and quit, while retaining the footer’s common actions.
- **Observed:** The operator initially found only Refresh and Quit in the run-list footer and no visible help popup. After discovering `Ctrl+P`, they liked the command palette and its command list. Source: operator account. [`RunListScreen.BINDINGS`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) exposes only Refresh and Quit in that screen’s footer; [`RunDetailScreen.BINDINGS`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) adds Back, Advance, Start, and Quit. The application does not add a visible Help binding or a help modal. The inline title currently combines identity and instruction: `Runs — click a row or press Enter to open`.
- **Friction cost:** Useful capabilities remain undiscoverable until an operator happens to know a framework shortcut; navigation copy competes with the screen title.
- **Touchpoints:** [`FoundryTuiApp`, `RunListScreen`, and `RunDetailScreen`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py); maintained keyboard list in [operator-runbook.md](../../operator-runbook.md#tui-mode-textual).
- **Interpretation:** The command palette already supplies the broad command inventory the operator wants. The missing piece is a visible affordance and Foundry-specific orientation—not a second, competing help system. The footer remains valuable as persistent help for frequent operations.
- **Options and tradeoffs:**
  - **Visible Help binding (`?`):** Open a compact Foundry help modal and mention `Ctrl+P` for all commands. Most explicit; duplicates palette content unless generated from bindings.
  - **Expose palette in the footer:** Add “Commands” with its shortcut, and let the palette remain the full help surface. Low duplication; framework command descriptions may not explain focus behavior or mouse equivalents.
  - **First-run hint:** Brief notification: “Press Ctrl+P for all commands.” Minimal chrome; easy to miss and can become noise.
- **Probe:** Start new users on the list without documentation and ask them to find all navigation commands; compare visible `?`, footer “Commands,” and one-time hint variants. Preserve Refresh/Quit footer entries in every variant.
- **Status:** open

### Run identity and progress metadata need a presentation layer

*Operator signal (paraphrased): The node title is useful, but the top stats and `v-002` need clearer formatting; most of Position is debug information.*

- **Expected:** A readable heading for the current step, a small set of meaningful run facts, and an explanation or omission of internal identifiers.
- **Observed:** The detail header is one dense line assembled by [`_update_summary`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py): `run=… phase=… status=… node=… revision=… wait=…`. The markdown starts `Steward context — shape.examine (v-002)`, then the human title and a Position block with run, visit, node, kind, and lifecycle ([`render_context_markdown`](../../../.cursor/foundry/cli/foundry_cli/render.py)). `v-002` is a sequential visit identifier generated by [`next_visit_id`](../../../.cursor/foundry/cli/foundry_cli/engine/lifecycle.py), not the count of visits to that node specifically.
- **Friction cost:** Operators must decode diagnostics before reaching the current task; `v-002` invites an understandable but incorrect “node visit count” interpretation.
- **Touchpoints:** [`RunDetailScreen._update_summary`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py); [`render_context_markdown`](../../../.cursor/foundry/cli/foundry_cli/render.py); node title in [`shape.examine/node.yaml`](../../../.cursor/foundry/nodes/shape.examine/node.yaml).
- **Interpretation:** The screen stacks two debug-oriented summaries—the host payload line and the steward packet’s Position section. Both are useful for diagnosis, but neither is an operator hierarchy.
- **Options and tradeoffs:**
  - **Operator header + details drawer:** Lead with title, run id, and action state; move revision, visit id, lifecycle, and raw node id under “Technical details.” Clear default; adds disclosure state and responsive layout work.
  - **Relabel in place:** `Run`, `Phase`, `Current step`, `Version`, `Needs`; annotate `Visit v-002`. Smaller change; the dense line remains.
  - **Debug toggle:** Default to operator mode, with a palette command to show raw protocol/context metadata. Strong audience split; must ensure support instructions can reliably ask users to enable it.
- **Probe:** Ask operators to identify current work, whether input is needed, and how to provide a support identifier using default vs details-expanded prototypes.
- **Status:** open

### Steward context is not yet an operator-readable run history

*Operator signal (paraphrased): Show what I provided at intake and what the model responded with; the Reads, Config, State, Artifacts, Allow, Files, Receipts, Operations, Examination, and Judgment sections are good debug information but not good primary information.*

- **Expected:** A narrative exchange: the original intake, the model’s examination response, and the resulting questions, with technical context available secondarily.
- **Observed:** The left pane is titled “Run history,” but each refresh displays the latest `run.context` markdown packet ([`RunDetailScreen._apply_context_markdown`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py)). [`render_context_markdown`](../../../.cursor/foundry/cli/foundry_cli/render.py) is explicitly a **steward context packet** and renders Position, Reads, Allow, Produces, Receipts, Worker, Operations, node guidance, and Judgment. [`_kv_table`](../../../.cursor/foundry/cli/foundry_cli/render.py) stringifies nested state into one table cell, explaining why content after keys such as `draft_ac` can appear visually jammed into the Key/Value table. The examine node declares intake ticket, clarifying questions, assumptions, decisions, and draft AC as state/artifact reads ([`shape.examine/node.yaml`](../../../.cursor/foundry/nodes/shape.examine/node.yaml)), so the underlying information exists but is organized for the steward rather than the operator.
- **Friction cost:** The primary pane spends most of its area on permissions and execution internals, obscures long model output in generic tables, and does not establish a clear intake → response → questions sequence.
- **Touchpoints:** [`render.py`](../../../.cursor/foundry/cli/foundry_cli/render.py); context assembly in [`context.py`](../../../.cursor/foundry/cli/foundry_cli/context.py); attach history requirement in [spec.md](spec.md#foundry-attach-interactive) AC 24 and 28.
- **Interpretation:** This is a contract mismatch, not only a Markdown styling bug. `run.context --markdown` was designed to tell a steward what it may read/do; labeling its latest packet “Run history” does not make it an operator transcript. The approved spec’s assumption that context markdown can back full history needs refinement.
- **Options and tradeoffs:**
  - **Purpose-built operator projection:** Compose cards/sections from intake ticket, accepted agent result, questions, answers, presentations, and decisions; expose the steward packet under “Technical context.” Best information hierarchy; requires a stable host projection or client-side event/state composition.
  - **Operator renderer for existing context:** Reorder and specially render ticket, `draft_ac`, assumptions, and questions before collapsing generic Reads/Allow sections. Faster; still represents only the latest node context, not full history.
  - **Event-sourced transcript:** Build history from ledger events plus linked artifacts/receipts. Faithful chronology; event schemas may not contain all human-readable model content and could require additional RPCs.
- **Probe:** Prototype one `shape.examine` fixture with (A) reordered context and (B) intake/model/question transcript. Measure whether operators can restate what they asked, what the model concluded, and what needs answering without opening technical details.
- **Status:** open

### Questions must remain readable and reachable at constrained widths

*Operator signal: “I can't read the questions to answer the questions.”*

- **Expected:** Full question text and answer fields remain readable, scrollable, keyboard reachable, and pointer reachable; the main content should not compete with the action required to continue.
- **Observed:** Three clarifying questions competed with the main display and were cut off. The divider did not drag. Arrow keys scrolled the main area; the first Tab moved focus somewhere the operator could not see, while the second reached the first answer field. Clicking fields worked. Source: operator account. The layout fixes the actions panel at width 40 and at most 42% with a static border; there is no draggable split control ([`RunDetailScreen.DEFAULT_CSS`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py)). Questions are `Label` widgets followed by `Input` widgets in a separate `VerticalScroll`; there is no explicit initial focus, focus order, focus styling, panel-resize binding, or narrow-screen breakpoint in [`_wait_panel_widgets`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py).
- **Friction cost:** This blocks the run’s required human action, not merely readability. Hidden focus also makes keyboard navigation feel unpredictable even when fields are technically reachable.
- **Touchpoints:** [`RunDetailScreen.compose`, `DEFAULT_CSS`, and `_wait_panel_widgets`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py); headless wait-field test in [`test_tui.py`](../../../.cursor/foundry/cli/tests/unit/test_tui.py), which verifies field existence but not question wrapping, visibility, focus, or constrained dimensions.
- **Interpretation:** A fixed side panel is suitable for short actions but not arbitrary question text. The interaction priority should invert at a human wait: questions and answers are the main task, while technical history becomes supporting context.
- **Options and tradeoffs:**
  - **Responsive stacked layout:** At `user_input`, place complete questions and fields below (or above) history at full width; stack automatically below a width threshold. Most robust; reduces simultaneous context.
  - **Resizable split:** Add keyboard and pointer resize with saved width. Flexible for power users; discoverability, accessibility, and Textual implementation complexity are higher.
  - **Question-focused mode/modal:** Enter a full-screen answer form, with a command to return to context. Guarantees readability; context switching may be awkward when an answer depends on the intake/model response.
  - **Minimum repair:** Increase panel width, wrap labels, focus the first unanswered field, scroll focused widgets into view, and add visible focus styling. Lower cost; three long questions can still overwhelm a side rail.
- **Probe:** Add headless tests at 80×24, 100×30, and 160×45 with three long questions. Assert complete question text is renderable, first Tab/focus is visible, every field scrolls into view, and pointer activation still works. Dogfood the stacked and resizable variants.
- **Status:** open

## Cross-cutting design opportunities

1. **One readiness story, two audiences:** Machine-readable dimensions (`--json`) are appropriate for automation; human output should default to outcome, next command, and failure-specific remediation (reusing preflight hint text where possible).
2. **Lifecycle vocabulary:** If `up` is promoted as the primary bootstrap, pair it with an equally visible stop surface (`down` or documented equivalent that stops both host and bridge) or rename `up` to language that does not imply symmetry (e.g. `foundry serve`) — mixing metaphors is costly.
3. **Help as curriculum:** Grouped help is a low-risk complement to spec work in [foundry-up](../foundry-up/); it benefits every workspace, not only first-run.
4. **CLI sync boundary:** Document and optionally split “create run” from “advance through judgment” so blocking, progress, and question presentation are explicit product choices—not accidental coupling in `cmd_shape`.
5. **Porcelain curriculum consistency:** `up`, `shape`, and `attach` should share verdict + **Next:** vocabulary, positional examples that actually parse, and one primary “watch the run” surface that renders markdown—not three different metaphors (telemetry, `run=`, JSON stream).
6. **One run console, truthful help:** Pick whether `tui` or upgraded `attach` is the listed “watch” command; fix nested `--help` so `run` subcommands are discoverable; disambiguate `runs` vs `run` in name or copy.
7. **Windows headless contract:** Any child process spawned during `up`, `down`, stop, or engine hooks should share the same no-window spawn policy as bridge/host start.
8. **Operator projection, not steward packet:** Treat the existing context markdown as technical detail. The primary attach view should project intake, model response, human questions/answers, and decisions into a readable sequence.
9. **Human action owns the layout:** When a run needs approval or answers, allocate the primary readable area and initial focus to that action; history and diagnostics should support it.
10. **One discoverability system:** Keep common footer actions, expose the command palette visibly, and generate any expanded shortcut help from the same bindings to avoid drift.

Prioritize readable/reachable questions and the operator-history projection before visual polish: the current side rail can block the required human action. Then address run-list language, metadata hierarchy, visible palette discovery, and win32 flash probes alongside the remaining attach/console work.

## Evidence index

| Item | Source |
|------|--------|
| `foundry up` sample output | Operator account (session) |
| `_format_up`, `cmd_up`, parser subcommands | Code snapshot under `.cursor/foundry/cli/` |
| Shutdown today | [operator-runbook.md](../../operator-runbook.md) — `foundry host stop`; no top-level `down` |
| Git comparison notes | [organized-cli.md](../organized-cli.md) |
| `foundry down` request | [foundry_up-now_down.md](../foundry_up-now_down.md) |
| Related first-run retro | [foundry-up/retro.md](../foundry-up/retro.md) |
| `foundry shape` → `user_input` (foundry-0004) | Operator account (session) |
| GWT expectations (`up`, shape positional, attach console) | Operator account (2026-10-15); [foundry-up.md](../foundry-up.md), [foundry-up/gwt-scenario.md](../foundry-up/gwt-scenario.md) |
| `attach` vs `shape --attach` (`human_questions`) | Code: [`foundry.py`](../../../.cursor/foundry/cli/foundry.py) vs [`cmd_attach`](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) |
| TUI run list click vs Enter | Operator account (2026-10-15); [`tui/app.py`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) |
| `runs` / `run` `--help` output | Operator account + `foundry runs --help` / `foundry run --help` on win32 |
| Windows console flashes | Operator account (2026-10-15); [`detached_spawn.py`](../../../.cursor/foundry/cli/foundry_cli/detached_spawn.py), [`bridge/lifecycle._terminate_pid`](../../../.cursor/foundry/cli/foundry_cli/bridge/lifecycle.py) |
| Interactive attach dogfood | Operator account (2026-10-16): running-run list and `shape.examine` detail with three clarifying questions |
| Attach list/detail implementation | [`tui/app.py`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py), [`test_tui.py`](../../../.cursor/foundry/cli/tests/unit/test_tui.py) |
| Steward markdown mechanism | [`render.py`](../../../.cursor/foundry/cli/foundry_cli/render.py), [`context.py`](../../../.cursor/foundry/cli/foundry_cli/context.py), [`shape.examine/node.yaml`](../../../.cursor/foundry/nodes/shape.examine/node.yaml) |
| evaluate-run | Not run for this session |
