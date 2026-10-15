# Operator experience — readiness output, shutdown, and help layout

Status: **open design investigation**. The operator dogfooded the Foundry registry workspace (`~/src/foundry`) after `foundry up` shipped. Observations below are from the operator’s account and a code snapshot of the CLI; they are not a run evaluation.

**Run evidence:** No `.foundry/runs/{run_id}` was supplied for this session. evaluate-run not run—engine verdict omitted.

Maintained operations: [operator-runbook.md](../../operator-runbook.md). Feature context for `foundry up`: [foundry-up/spec.md](../foundry-up/spec.md).

## Purpose and setting

The operator wanted a quick, trustworthy answer to “is Foundry running and healthy in this workspace?” after `foundry up`, plus a mental model for turning local services off. They also compared top-level `foundry` help to `git` and asked for flow-oriented grouping so commands are easier to find at the right moment in a workflow.

## Experience in the operator's terms

`foundry up` returned accurate readiness facts in a line-oriented `key=value` style. The operator could see bridge URL, host PID, and health RPC success, but had to translate internal names (`bridge`, `adapter`, `ready`, repeated `ok=True`) into “I can run `shape` now.” Running `up` created a strong expectation that `foundry down` exists; discovering shutdown meant reading the runbook or inferring from `host` subcommands. Running bare `foundry` listed every subcommand alphabetically in argparse order, which is complete but not ordered by the operator journey (bootstrap → local services → shape a run → attend gates → inspect).

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

## Cross-cutting design opportunities

1. **One readiness story, two audiences:** Machine-readable dimensions (`--json`) are appropriate for automation; human output should default to outcome, next command, and failure-specific remediation (reusing preflight hint text where possible).
2. **Lifecycle vocabulary:** If `up` is promoted as the primary bootstrap, pair it with an equally visible stop surface (`down` or documented equivalent that stops both host and bridge) or rename `up` to language that does not imply symmetry (e.g. `foundry serve`) — mixing metaphors is costly.
3. **Help as curriculum:** Grouped help is a low-risk complement to spec work in [foundry-up](../foundry-up/); it benefits every workspace, not only first-run.
4. **CLI sync boundary:** Document and optionally split “create run” from “advance through judgment” so blocking, progress, and question presentation are explicit product choices—not accidental coupling in `cmd_shape`.

Prioritize `shape` parking UX (show questions + explain blocking) and readiness copy for operators who already run `up` daily; grouped help helps newcomers.

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
| evaluate-run | Not run for this session |
