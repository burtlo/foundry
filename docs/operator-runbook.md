# Operator runbook — application workspace

This guide is for the **application repository** that contains `.foundry/foundry.yaml` (registry pointer) and `.foundry/runs/`. Commands invoke the Foundry CLI from that workspace root unless you pass `--workspace`.

**Related docs:** [Agent adapter configuration](concepts/agent-adapter.md), [Implementation flow runtime](features/implementation-flow-runtime.md), [Job host architecture](concepts/job-host-architecture.md), [CLI reference](cli/index.md).

## Global flags

These flags may appear before any subcommand:

| Flag | Purpose |
|------|---------|
| `--workspace <path>` | Application repo root (default: current directory) |
| `--registry <path>` | Foundry bundle root (usually only when `.foundry/foundry.yaml` is missing; prefer config-based resolution) |
| `--json` | Machine-readable JSON envelope on stdout |

Example:

```bash
foundry --json --workspace /path/to/app status my-run-slug
```

## Prerequisites

Run these once per workspace (or after changing registry or app manifest):

1. **Registry pointer** — validates `.foundry/foundry.yaml`:

   ```bash
   foundry config validate
   ```

2. **Application manifest** — validates `.foundry/app.yaml`:

   ```bash
   foundry app validate
   ```

3. **Job host** — durable advance, agent dispatch, and most user commands go through the local host when it is running:

   ```bash
   foundry host start
   foundry host status
   ```

   **Hands-off advancement** (judgment + host steps without manual `run advance`):

   ```bash
   foundry host start --auto-advance
   ```

   Requires `FOUNDRY_AGENT_ADAPTER` / bridge for `wait.kind=agent`. The daemon never auto-`decide` or auto-`answer`.

   Stop with `foundry host stop`. Foreground mode (tests): `foundry host run --auto-advance`.

   **Observe the host:** `foundry host status` (includes auto-advance tick summary when enabled). Logs: `foundry host logs` or `foundry host logs -f` (writes to `.foundry/host/host.log`).

If `config validate` fails with a missing registry, run `foundry config init` (see [config-init](cli/config-init.md)) or add `.foundry/foundry.yaml` manually.

### Judgment / agent adapter (later phases)

For production judgment tasks (`shape.examine`, `shape.present`, and similar), the host should use the HTTP adapter:

| Variable | Role |
|----------|------|
| `FOUNDRY_AGENT_ADAPTER=http` | Select HTTP transport |
| `FOUNDRY_AGENT_HTTP_URL` | URL of the agent endpoint (e.g. `http://127.0.0.1:8791/v1/agent`) |

See [agent-adapter.md](concepts/agent-adapter.md) and [judgment-bridge.md](features/judgment-bridge.md).

**Production judgment (shipped):**

```bash
export FOUNDRY_CURSOR_API_KEY=...   # bridge process only
foundry bridge start                # from application workspace; default :8791/v1/agent
export FOUNDRY_AGENT_ADAPTER=http
export FOUNDRY_AGENT_HTTP_URL=http://127.0.0.1:8791/v1/agent
foundry host start                  # host must inherit FOUNDRY_AGENT_*
```

Until the bridge is running, use `FOUNDRY_ALLOW_STUB_ADAPTER` only in local/CI per the adapter doc, or submit results with `foundry run agent submit`.

### Long `run advance` through the host

When the job host is running, `foundry run advance`, `foundry shape`, and `foundry start` call the host RPC `run.advance`. A single call may run several automatic steps and **multiple judgment dispatches**. Per-task model timeouts live in the registry (`limits.timeout_seconds` on judgment tasks under `.cursor/foundry/tasks/` — today up to **300s** for `verify.acceptance`). The CLI client uses a **longer socket timeout** so the host can finish the full advance:

`base_slack + step_budget × (max_judgment_timeout + per_round_slack)`

Defaults: `base_slack` 10s, `per_round_slack` 15s, `max_judgment_timeout` = max of judgment task limits in your resolved registry. Implementation: `foundry_cli/host/timeout_policy.py`.

**Operator overrides** (optional) in `.foundry/host.yaml`:

```yaml
schema_version: 1
advance_client:
  base_slack_seconds: 10
  per_round_slack_seconds: 15
  judgment_max_seconds: 300   # optional; default = registry max
  max_seconds: 3600           # optional cap on total client socket timeout
```

Environment overrides (host/CLI process): `FOUNDRY_HOST_CLIENT_JUDGMENT_MAX_SECONDS`, `FOUNDRY_HOST_CLIENT_BASE_SLACK_SECONDS`, `FOUNDRY_HOST_CLIENT_PER_ROUND_SLACK_SECONDS`, `FOUNDRY_HOST_CLIENT_MAX_SECONDS`.

Requirements:

- **`foundry host start`** must stay up for the full advance (do not stop the host mid-call).
- With **`FOUNDRY_AGENT_ADAPTER=http`**, the **judgment bridge** (or other endpoint at `FOUNDRY_AGENT_HTTP_URL`) must be reachable for the same duration.
- Optional RPC param: `client_timeout_hint_seconds` on `run.advance` raises the client timeout floor for custom clients.

If advance fails with a host connectivity error after tens of seconds, check host logs under `.foundry/host/`, bridge latency, and whether `advance_client.max_seconds` or env caps are too low before lowering `--step-budget`.

## Start a new implementation run (Shape)

Create a run from a verbatim shape request and advance into Shape:

```bash
foundry shape --input "Add export to CSV on the reports page"
```

Alternatives: `--input-file path/to/request.txt`, optional `--run-id`, `--flow implementation`.

The command creates the run under `.foundry/runs/` and advances until the engine parks on a wait or step budget. Note the run id in output (or use `foundry runs --json`).

## Attach and detach

Watch snapshot and stream ledger events:

```bash
foundry attach <run_id>
```

Press **Ctrl-C** to detach; the run and host keep going. Use `--no-follow` for a one-shot snapshot (and events when `--json`). `--after-seq N` resumes the event stream after sequence `N`.

## Answer clarifying questions

When `wait.kind` is `user_input`:

1. Inspect wait and question ids:

   ```bash
   foundry status <run_id> --json
   ```

2. Submit answers (JSON object keyed by question id):

   ```bash
   foundry answer <run_id> --answers '{"q1": "Use REST", "q2": "PostgreSQL"}'
   ```

3. If the run does not move automatically, advance:

   ```bash
   foundry run advance --run <run_id>
   ```

Optional: `--revision` for optimistic concurrency; `--local` to bypass the host.

## User gate decisions

When `wait.kind` is `decision`, pick one of the gate option values shown in status:

```bash
foundry decide <run_id> accept
```

(`accept` is an example; use the actual option slug from the gate.)

**Important:** `decide` records the decision but does **not** auto-advance. Follow with:

```bash
foundry run advance --run <run_id>
```

Legacy equivalent: `foundry gate decide --run <run_id> --decision <option>`.

## Run status and listing

**One run** (default: sole non-terminal run if id omitted):

```bash
foundry status
foundry status <run_id> --json
```

**All workspace runs:**

```bash
foundry runs --json
```

**Snapshot summary via host** (when running):

```bash
foundry run get --run <run_id> --json
```

**Steward context** (markdown or JSON):

```bash
foundry run context --run <run_id> --markdown
```

## Execute phase: `start` and advance

After Shape completes, the flow parks at **`execute.start`** until you authorize execution:

```bash
foundry start <run_id>
```

That records execute authorization and advances into **`execute.intake`**. Host-owned mechanism steps then require further advancement:

```bash
foundry run advance --run <run_id>
```

Repeat `run advance`, or start the host with `--auto-advance`, until the next wait. Use `foundry attach <run_id>` or `foundry host logs -f` to watch progress during long stretches.

`run advance` flags (see [run-advance](cli/run-advance.md)):

| Flag | Default | Purpose |
|------|---------|---------|
| `--run` | — | Run id (or use `--run-dir`) |
| `--step-budget` | 8 | Max automatic steps per invocation |
| `--revision` | — | Expected snapshot revision |
| `--local` | false | Advance on disk even when host is running |

## `wait.kind` → what to run

| `wait.kind` | Meaning | Operator action |
|-------------|---------|-----------------|
| `decision` | User gate open | `foundry decide <run> <option>` then `foundry run advance --run <run>` |
| `user_input` | Clarifying questions | `foundry answer <run> --answers '{...}'` then `run advance` if needed |
| `operator` | Halt, limit, or error needs human fix | Fix cause (retry, config, repo state); `foundry retry <run>` or `foundry cancel <run> --reason "..."` as appropriate; then `run advance` |
| `agent` | Judgment task dispatched or pending | With HTTP adapter + bridge: `run advance` (host invokes adapter). Without adapter: `foundry run agent submit --run <run> --request-id <ar_…> --result-file result.json` |
| *(null)* | Host may advance | `foundry run advance --run <run>` |

## Deliver and handoff

The implementation flow ends at **`deliver.stub`**, a terminal node. Foundry records deliver handoff state; it does **not** open pull requests or push to remotes. Humans own git push, PR creation, and release steps after the run reaches `completed`.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Commands hang or fail against host | `foundry host status`; start host; avoid `--local` unless intentional |
| Stale revision errors | Re-run `status --json`, pass `--revision` on mutating commands |
| Agent waits never complete | Adapter env on host; bridge URL; or manual `run agent submit` |
| Long `run advance` times out | Client uses extended timeout (`timeout_policy.py`); keep host and judgment bridge running for the full advance; check `.foundry/host/` logs |

## Host read API (TUI and integrations)

The job host exposes read RPCs so clients do not subprocess `foundry run context`:

| RPC | CLI equivalent | Notes |
|-----|----------------|-------|
| `run.get` | `run get` | Includes `phase`, `wait_kind`, `status_reason` |
| `run.context` | `run context` | `format`: `json` or `markdown` |
| `run.events` | `run events` | `after_seq`; optional `block_ms` long-poll (`timed_out`) |

Use `call_host` from the CLI bundle or the same JSON line protocol over the host socket. Combine `run.events` long-poll with periodic `run.get` when `timed_out` is true — events track the ledger, not every revision change. Full contract: [host TUI protocol](features/host-tui-protocol.md).

## TUI mode (Textual)

The **host-only** Textual UI talks to the job host over the same RPCs as the CLI (`run.list`, `run.get`, `run.context`, `run.events`, `run.decide`, `run.answer`, `run.start`, `run.advance`). It does not embed the workflow engine.

**Prerequisites:** `pip install textual` (included in `.cursor/foundry/cli/requirements.txt`), valid Foundry config, and a running host (the TUI can offer to start one).

```bash
foundry host start
foundry tui
foundry tui --run <run_id>
```

**Screens:** run list; run detail with status/wait panel, ledger event log (`run.events` with long-poll), and steward context markdown (`run.context`). The detail view polls the host every ~2s and refreshes status, wait panel, and context when revision or wait state changes (including host auto-advance). Host RPCs run off the UI thread.

**Actions (keyboard):**

| Key | Action |
|-----|--------|
| `Enter` | Open selected run (list screen) |
| `Esc` | Back to run list |
| `r` | Refresh run, context, and events |
| `a` | `run.advance` (uses host client timeout policy) |
| `s` | `run.start` + advance at `execute.start` |

Wait panels expose buttons for gate **decide** options and **answer** fields for `user_input` waits (no raw `gate decide` / `visit` commands).

Feature record: [foundry-tui.md](features/foundry-tui.md).

## Integration smoke

Validates the **production-shaped** stack without manual steps: judgment bridge (mocked Cursor SDK by default), job host with `FOUNDRY_AGENT_ADAPTER=http`, optional auto-advance, `run create`, and `run advance` through Shape to **`shape.present.gate`** (`wait_kind: decision`).

```bash
just integration-smoke
# or from the CLI package:
cd .cursor/foundry/cli && .venv/bin/python -m foundry_cli.operator_integration_smoke
```

Flags: `--real-cursor` (requires `FOUNDRY_CURSOR_API_KEY`), `--no-auto-advance`, `--workspace` / `--registry`.

CI: `tests/unit/test_operator_integration_smoke.py` (pytest xdist group `operator_integration_smoke`).

## Program index

Operator integration program (**complete**, phases 0–6): [plans/operator-integration-program.md](plans/operator-integration-program.md).
