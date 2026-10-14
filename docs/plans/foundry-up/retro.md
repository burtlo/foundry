# Operator experience — first porcelain workspace

Status: **open design investigation**. This records the operator's experience during the first porcelain workspace setup. Commands and symptoms below are historical observations; code links identify the implementation inspected for this retro and may move as the project changes. [The operator runbook](../../operator-runbook.md) is the maintained source for how to operate Foundry.

## Purpose and experience

The operator wanted to get from a sibling application repository (`~/src/porcelain`, alongside `~/src/foundry`) to a working `shape` run. The path required bootstrapping `.foundry/`, finding the CLI in the Foundry repo, starting a bridge in the application workspace, starting a host with inherited adapter environment, and then running `shape`. Much of that composition was visible only after trying commands and inspecting failures. The product demanded knowledge of its internal process boundaries before the operator could do the first useful thing.

This is product feedback, not an assessment of advice in the conversation. The earlier account of what a “steward” said first did not accurately represent what the operator wants to preserve.

## Feedback investigations

### 1. A first run requires assembling several systems by hand

*Operator signal (paraphrased): Why do I have to start and connect several pieces before I can run `shape`?*

**Status:** open.

**Operator signal and impact.** The path from an empty app repo to a working judgment call felt fragmented. The operator had to discover `just setup` in the registry, `config init` / `app discover` / `app init` in the application, a non-global `foundry.sh`, and separate bridge and host processes. The bridge needed the app workspace; the host needed `FOUNDRY_AGENT_ADAPTER` and `FOUNDRY_AGENT_HTTP_URL` in *its startup environment*. Exporting them only before `shape` did not change a running host. This created restart cycles and uncertainty about which terminal owned what.

**Observed path.** Validation succeeded, but an early `shape` failed with `HOST_ERROR: No agent adapter configured`. A bridge started from the Foundry repo announced the Foundry workspace rather than porcelain. Starting it from porcelain corrected the workspace. These observations explain the friction; they are not a claim that the chat transcript itself is the product defect.

**System touchpoints.** [`cmd_bridge_start`](../../../.cursor/foundry/cli/foundry_cli/bridge_commands.py) obtains its workspace from `CommandContext`. [`cmd_host_start`](../../../.cursor/foundry/cli/foundry_cli/host_commands.py) spawns a separate process, so its environment is captured at start. [`cmd_shape`](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) creates and advances a run through that host. The operator-facing contract lives in the [runbook](../../operator-runbook.md) and [agent adapter concept](../../concepts/agent-adapter.md).

**Design interpretation.** The interface exposes service topology at the moment the user expects one workflow action. The operator must understand `cwd`, environment inheritance, and process lifetime before getting feedback on the application idea.

**Directions to explore.** A single supervised `foundry up` could resolve workspace, bridge, adapter URL, and host lifecycle, then show readiness for judgment. A smaller repair could add a preflight to `shape` and `host start` that reports which dependency is missing and how the running host was configured. The supervisor reduces terminal choreography but adds lifecycle and secret-handling responsibilities; preflight is cheaper but leaves the choreography in place. Test both designs against the first-run path, including restart and wrong-workspace cases.

### 2. Successful commands look like errors

*Operator signal (paraphrased): Did my validation succeed, or is `error [None]: None` telling me it failed?*

**Status:** open.

**Operator signal and impact.** `config validate`, `app validate`, `cli resolve`, and `host logs` printed `error [None]: None` in ordinary output even when the JSON result reported success. The operator switched to `--json` to establish whether commands had worked. This undermined trust in every subsequent CLI result.

**Observed mechanism.** [`FORMATTER_REGISTRY` and `_format_result`](../../../.cursor/foundry/cli/foundry.py) print a registered human formatter for some successful commands, then fall through to `_format_error` for unregistered successes. This is a code-backed explanation of the symptom at the time of review.

**Directions to explore.** Add a coherent default success renderer for all commands, and test representative command families through the actual CLI output path. A one-line `ok` fallback fixes false error language; command-specific summaries would better answer “what changed?” but cost more maintenance. Define the information contract for successful read-only, mutating, and streaming commands before adding individual formatters.

### 3. Host failures are hard to distinguish from stale state

*Operator signal (paraphrased): Is my host actually running, and which failure belongs to this attempt?*

**Status:** open.

**Operator signal and impact.** `host start` from the app workspace failed before publishing discovery state; logs showed `ModuleNotFoundError: No module named 'foundry_cli'`. Setting `PYTHONPATH` allowed startup. Later, `host status --json` could report `running: false` with a stale PID, while another start could report `already_running: true` alongside `running: false`. The log mixed an untimestamped first failure with later timestamped lines and earlier attempts.

**System touchpoints.** [`_spawn_detached` and `cmd_host_start`](../../../.cursor/foundry/cli/foundry_cli/host_commands.py) launch `python -m foundry_cli.host` with `cwd` set to the application workspace and append stderr to the host log. Host discovery and health checks live under [`host/`](../../../.cursor/foundry/cli/foundry_cli/host/). These links give future work an entrypoint; the historical observations need a fresh reproduction before calling every state combination a current defect.

**Design interpretation.** The CLI combines three different concepts—process exists, host is healthy, and host is ready for judgment—into status words that are too easy to read as equivalent.

**Directions to explore.** Package the host so detached startup does not depend on caller `PYTHONPATH`; publish a startup failure with the log path and causal error; make status report process, health, and adapter readiness separately. A daemon supervisor could also own stale process cleanup. The narrow packaging fix addresses one failure; a lifecycle model addresses the broader ambiguity. Probe startup from a clean sibling app and from stale PID/socket states.

### 4. A successful agent response was reported as bridge failure

*Operator signal (paraphrased): Why did my `shape` run fail after the agent call seemed to finish?*

**Status:** fixed-in-code for the `finished` status mismatch; diagnostic experience remains open.

**Operator signal and impact.** A `shape` attempt reached the bridge and Cursor SDK, then the bridge returned 502 with `RuntimeError: Cursor agent run failed with status 'finished'`. From the operator's view, a successful upstream call became an opaque workflow failure.

**System touchpoint and current state.** [`cursor_provider.invoke_judgment`](../../../.cursor/foundry/cli/foundry_cli/judgment_bridge/cursor_provider.py) was identified in the session as rejecting the SDK's `finished` status. The current provider includes `finished` among successful statuses, so this specific mismatch appears fixed. The historical failure still shows how little diagnostic context reached the operator.

**Directions to explore.** Keep contract tests against real SDK response shapes and preserve the upstream status in structured diagnostics. Decide what the operator should see when judgment transport succeeds but result validation fails; a generic 502 does not support recovery.

### 5. Logs and status do not tell a clear story of the current attempt

*Operator signal (paraphrased): Is my setup ready now, and why does `host status` feel slow?*

**Status:** open; the source of the perceived delay has not been measured.

**Operator signal and impact.** `host logs` had no header identifying the file, process, or time range, and retained older failures. The operator also perceived `host status` as slow while the bridge and host were running. The delay source was not established in the session.

**System touchpoints.** [`cmd_host_logs` and `cmd_host_status`](../../../.cursor/foundry/cli/foundry_cli/host_commands.py) are the CLI entrypoints; [`host_status_payload`](../../../.cursor/foundry/cli/foundry_cli/host/client.py) computes status, and [`read_log_tail`](../../../.cursor/foundry/cli/foundry_cli/host/log_reader.py) reads the accumulated log.

**Directions to explore.** Correlate log lines with a host start ID, show current process and log path in `host logs`, and distinguish current startup errors from history. Measure `host status` latency by discovery, socket health, and bridge checks before choosing a performance fix. Correlation metadata makes logs easier to trust but requires a stable start ID across process and CLI boundaries; a lightweight header is cheaper but cannot separate mixed attempts. A richer status view could answer the operator's immediate question: “Is this setup ready for my next command?”

## Cross-cutting opportunity

The recurring problem is **readiness is distributed across commands and processes**. A useful design test is whether a new operator can run one documented setup action, receive a trustworthy readiness summary, invoke `shape`, and understand the next action without learning the bridge/host topology. Fixing formatting and import bugs is necessary, but the larger opportunity is to make that operator journey an explicit product surface.

### Probes for next session

- Start from a clean sibling app workspace and record every prerequisite the operator must discover before the first `shape` judgment.
- Time `host status` with bridge absent, bridge ready, and a stale host discovery record to isolate the perceived delay.
- Test a readiness summary that reports workspace, host, adapter, and bridge separately before running `shape`.

## Evidence index

| Interaction observed in the session | Operator-visible outcome |
|---|---|
| `just setup`; `config validate`; `app validate` | Setup and validation succeeded; ordinary success output was misleading |
| `host start` from porcelain | Import failure before discovery until `PYTHONPATH` was set |
| `shape --input-file tooling-001.md` before host adapter configuration | `HOST_ERROR: No agent adapter configured` |
| `bridge start` from Foundry, then porcelain | First bridge used the wrong workspace; second used the app workspace |
| `shape` through configured host and bridge | SDK call returned, then bridge emitted 502 for status `finished` |
| `host status --json`; `host logs` after failures | Stale or contradictory state and mixed historical log lines |

The run correctness and judgment record belong in `/evaluate-run` results when a specific run is bound to this experience. This retro records what the run artifacts alone cannot explain: the commands tried, the operator's expectations, and the systems that made the path difficult.
