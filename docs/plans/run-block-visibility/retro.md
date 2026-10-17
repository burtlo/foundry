# Run block visibility — any parked node, not just execute intake

Status: **open design investigation**. The operator reported difficulty understanding **why a run is blocked on any node** without manually opening run artifacts, snapshot fields, or host logs. **`execute.intake`** was the first painful example; the desired fix is **run-wide**, not intake-specific.

**Run evidence:** No `.foundry/runs/{run_id}` or archive path was supplied for this session. **evaluate-run not run—engine verdict omitted.**

Maintained operations: [operator-runbook.md](../../operator-runbook.md). Adjacent UX bundle: [cli-operator-ux/retro.md](../cli-operator-ux/retro.md) (attach, operator history, technical context toggle). Engine halt/wait model: [implementation-flow-runtime.md](../../features/implementation-flow-runtime.md), [`run_status_reason.py`](../../../.cursor/foundry/cli/foundry_cli/engine/run_status_reason.py).

## Purpose and setting

The operator drives or watches **implementation-flow** runs across shape, execute, and verify. Whenever the run **stops advancing**—blocked intake, failed lifecycle check, repair/reverify limits, unsupported host step, agent error, gate halt—they need an immediate answer to **“what is wrong and what do I do next?”** Today that answer is scattered across JSON fields, steward markdown, receipt files, and host logs rather than the primary feed they already have open (CLI status, TUI run view).

## Experience in the operator's terms

The run looks “stuck” or “blocked” in the header or status line, but the **error text and checklist** are not in the main narrative. The operator opens `.foundry/runs/<id>/` (assessment, receipts, snapshot), `.foundry/host/host.log`, or toggles buried diagnostics to learn what failed—then guesses whether to **advance**, **retry**, **decide**, or fix workspace state. They recall a **panel beside the main run view** that used to surface what was going wrong; that affordance is gone or hidden. **Preferred end state:** the block explanation and **Retry** / **Advance** (and other lawful actions) live **in the main feed**, not only in a secondary debug strip—though a side panel could still host fuller steward context for those who want it.

## Feedback investigations

### “Blocked” does not explain what failed (any node)

*Operator signal: “I really can't tell why a run is blocked.”* (Follow-up: **not just** `execute.intake`—**any** blocking node.)

- **Expected:** Status, run list, attach, and TUI show **node**, **typed reason** (`status_reason` / halt), and a **human message** (findings, check failures, gate reject text) without opening the run directory.
- **Observed:** Human [`_format_status`](../../../.cursor/foundry/cli/foundry.py) prints run id, phase, status, node, revision, and optionally `wait=<kind> summary='…'`. It does **not** print `status_reason` or `halt_reason`, though [`cmd_status`](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) returns them in JSON. [`_format_runs`](../../../.cursor/foundry/cli/foundry.py) lists `wait_kind` only. Multiple engine paths set reasons: blocked intake ([`blocked_intake.py`](../../../.cursor/foundry/cli/foundry_cli/engine/blocked_intake.py)), lifecycle halts ([`lifecycle.py`](../../../.cursor/foundry/cli/foundry_cli/engine/lifecycle.py)), repair limits ([`run_status_reason.py`](../../../.cursor/foundry/cli/foundry_cli/engine/run_status_reason.py) `REPAIR_LIMIT_EXCEEDED`, etc.). Source: operator account; code snapshot.
- **Friction cost:** Same inspection loop on every phase; operators cannot tell operator-wait vs user gate vs halt without archaeology.
- **Touchpoints:** [`run_status_reason.py`](../../../.cursor/foundry/cli/foundry_cli/engine/run_status_reason.py); wait labels [`run_labels.py`](../../../.cursor/foundry/cli/foundry_cli/run_labels.py); context JSON [`context.py`](../../../.cursor/foundry/cli/foundry_cli/context.py) attaches `status_reason` but [`render.py`](../../../.cursor/foundry/cli/foundry_cli/render.py) does not render it in markdown.
- **Interpretation:** The product **records** block reasons on the snapshot consistently enough for automation; **porcelain projection is wait-summary-first** and treats detailed messages as opt-in JSON or files.
- **Options and tradeoffs:**
  - **Shared “parked run” card** from `status_reason` + `wait` + active node (one helper for CLI + TUI + operator history). Covers all nodes; needs copy rules per code.
  - **Status-only fix** (print `message` when set). Fast; TUI/attach still lag.
  - **Verbose subcommand** (`status --diagnose`). Does not meet “right there in the feed” preference.
- **Probe:** Seed halts at execute intake, repair limit, and verify intake; ask operators to name fix + next command using only human `status` vs prototype card.
- **Status:** open

### Validation and intake issues are computed but not in the operator feed

*Operator signal: “There are these issues with the execute.intake and I can't see what they are…”* (Representative of **any** node that seals blocked receipts or sets findings.)

- **Expected:** The same **findings list** the host used appears in the main operator feed (and status), not only under `receipts/`.
- **Observed:** Example: [`_validate_frozen_shape`](../../../.cursor/foundry/cli/foundry_cli/engine/execute_step_executor.py) → `assessment.md` + `INTAKE_BLOCKED` + generic operator wait summary ([`blocked_intake.py`](../../../.cursor/foundry/cli/foundry_cli/engine/blocked_intake.py)). Verify intake and other steps have parallel finding lists ([`verify_step_executor.py`](../../../.cursor/foundry/cli/foundry_cli/engine/verify_step_executor.py)). [`build_operator_history_sections`](../../../.cursor/foundry/cli/foundry_cli/operator_history.py) does not project blocked-step findings. Source: operator account; [`test_rel011_blocked_intake_recovery.py`](../../../.cursor/foundry/cli/tests/unit/test_rel011_blocked_intake_recovery.py).
- **Friction cost:** High file/log tax for data the engine already computed.
- **Touchpoints:** Node docs under [docs/nodes/](../../nodes/); operator history; render path for steward context.
- **Interpretation:** Findings are **audit artifacts first**, **operator UI second**—inverted from the operator’s priority when parked.
- **Options and tradeoffs:**
  - **Operator-history section `blocked` or `parked`** when `status_reason` or blocked receipt present (read message / assessment, do not re-validate).
  - **Enrich wait.summary** with findings (truncated). Surfaces everywhere wait is shown; noisy for long lists.
  - **Fail earlier at CLI** (e.g. before `start`). Reduces mystery runs; not universal across in-run halts.
- **Probe:** Compare time-to-fix with findings in main feed vs files-only.
- **Status:** open

### TUI: no main-feed block card; operator waits unsupported; Advance/Retry missing

*Operator signal: “There used to be a display to the right of the main display” for errors; “ideally it would be right there in the main feed with the options there to **retry** and **advance**.”*

- **Expected:** While blocked, the run view shows **what happened** (error message, checklist, node title) and **primary actions** (Advance when lawful, Retry when `retry_eligible`, Decide/Answer when those waits apply)—in the **same scrollable operator history**, not behind a separate debug workflow.
- **Observed:** [`RunDetailScreen`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) layout: header summary (`run_id · step · Status · Needs`), then `#context-markdown` (operator history), then `#wait-panel`, then hidden `#technical-markdown`. **Technical context** is toggled via “Show technical context” and loads full steward [`run_context_markdown`](../../../.cursor/foundry/cli/foundry_cli/tui/host_client.py)—stacked in the scroll area when visible, **not a persistent right column** in the current snapshot. [`_wait_panel_widgets`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) builds UI only for `wait_kind` **`decision`**, **`user_input`**, and **`execute.start`** authorization—not **`operator`** (blocked intake, unsupported step, work-prompt waits). Header shows **Needs: Action** via [`needs_label`](../../../.cursor/foundry/cli/foundry_cli/run_labels.py) but the wait panel stays empty for `operator`. An `#advance-btn` handler exists ([`action_advance_run`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py)) but **no Advance button is mounted** in the wait panel ([`test_tui.py`](../../../.cursor/foundry/cli/tests/unit/test_tui.py) asserts zero `#advance-btn`). **No TUI wiring for `foundry retry`** (grep). Keyboard binding `a` → advance remains, but without visible affordance or block context. Source: operator account (right-panel memory); code snapshot 2026-10-16.
- **Friction cost:** TUI feels empty at the exact moment the run is blocked; operators fall back to files/logs or rediscover CLI commands; prior side-panel mental model no longer matches UI.
- **Touchpoints:** TUI [`app.py`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py); cli-operator-ux [spec.md](../cli-operator-ux/spec.md) D14 (operator history), D15 (technical context behind header control); host client advance/retry RPCs.
- **Interpretation:** Recent TUI work optimized **shape examine** waits (questions, gates) but **did not generalize “parked with reason”** for engine halts and `operator` waits. Technical context is the **steward packet** (instructions, reads, receipts)—heavy for “why blocked,” and off by default. The operator is asking for a **first-class block strip in the main feed**, with optional side/bottom panel for full diagnostics—not the inverse.
- **Options and tradeoffs:**
  - **Main feed (preferred):** Append operator-history section **“Run paused”** with `status_reason.message`, bullet findings, and buttons **Advance** / **Retry** (when eligible) / link to technical context. Matches chat-style “what’s wrong + what to tap.”
  - **Restore split layout:** `Horizontal` with operator history (left) and **diagnostics pane** (right): block summary + metadata + toggleable steward markdown. Recalls “display to the right”; costs horizontal space and Windows terminal width.
  - **Auto-open technical context on halt:** Surfaces steward packet without new projection; still steward-noisy and does not add Retry/Advance buttons.
  - **Wait-panel branch for `operator`:** Minimal: static reason + Advance button; does not unify all halt types unless driven by shared card helper.
- **Probe:** Blocked execute intake in TUI: measure whether operators find reason + next step with (A) today, (B) main-feed card only, (C) right pane only. Ask which layout they trust for retry vs advance.
- **Status:** open

### Operator wait “Action” without checklist or actions

*Operator signal (paraphrased): I see Needs: Action but not what to do.*

- **Expected:** **Action** waits show enumerated blockers and mounted controls (Advance after fix, Retry when engine allows).
- **Observed:** Generic wait summaries for `intake:blocked:*` and unsupported nodes; TUI wait panel empty for `operator`. Runbook lacks a halt-code table at time of writing.
- **Friction cost:** Label implies interactivity; UI provides none for the common blocked-intake case.
- **Touchpoints:** [`wait_state.py`](../../../.cursor/foundry/cli/foundry_cli/engine/wait_state.py); [`node_capability.py`](../../../.cursor/foundry/cli/foundry_cli/engine/node_capability.py) unsupported operator waits; P7 shape CLI `INTAKE_BLOCKED` vs execute-phase operator wait asymmetry.
- **Interpretation:** Wait **kind** is modeled; wait **presentation and actions** are only implemented for gate and Q&A shapes.
- **Options and tradeoffs:** Template map `request_ref` / `status_reason.code` → markdown + buttons vs one generic card fed only by `status_reason`.
- **Probe:** Same as TUI probe; track mis-clicks on Decide when blocked on engine step.
- **Status:** open

## Cross-cutting design opportunities

1. **One “parked run” projection, all surfaces:** Derive display from `active_node_id`, `wait`, `status`, `status_reason`, and (when present) sealed receipt / assessment paths. Use in human status, operator history markdown, TUI main feed, and optionally a side diagnostics pane.
2. **Actions beside explanation:** Advance ([`run advance`](../../../.cursor/foundry/cli/foundry_cli/user_cli.py)), Retry ([`retry_run`](../../../.cursor/foundry/cli/foundry_cli/engine/operator.py) / CLI `retry` when `retry_eligible`), Decide/Answer/Start already have host RPCs—TUI should mount buttons when the engine says the transition is legal, not only for gates and Q&A.
3. **Main feed vs side panel:** Operator **prefers main feed** for block + actions; **side (or toggled) panel** remains valuable for full steward context ([cli-operator-ux](../cli-operator-ux/spec.md) D15)—default **on** for block summary, steward detail **opt-in**, avoids repeating the “attach is JSON / context is elsewhere” cliff.
4. **Not intake-specific:** Any halt setting `status_reason` or parking with `operator` / `halted` status should use the same card; node-specific detail is in `message` and artifacts, not separate UX per node id.
5. **Bundle relationship:** Likely extends or revises cli-operator-ux P16–P21 (wait labels, operator history, attach/TUI). This bundle keeps the **cross-node block visibility** narrative for `/retro-feature-interview`.

**Suggested build order (hypothesis):** shared projection helper → operator history + human status → TUI main-feed card with Advance/Retry → optional split-pane diagnostics revival.

## Evidence index

| Kind | Reference |
|------|-----------|
| Operator account | This chat (`/capture-product-feedback`, 2026-10-16; TUI layout follow-up same session) |
| Halt / reason model | [`run_status_reason.py`](../../../.cursor/foundry/cli/foundry_cli/engine/run_status_reason.py), [`lifecycle.py`](../../../.cursor/foundry/cli/foundry_cli/engine/lifecycle.py), [`blocked_intake.py`](../../../.cursor/foundry/cli/foundry_cli/engine/blocked_intake.py) |
| Status porcelain gap | [`foundry._format_status`](../../../.cursor/foundry/cli/foundry.py), [`user_cli.cmd_status`](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) |
| Render / history gap | [`render.py`](../../../.cursor/foundry/cli/foundry_cli/render.py), [`operator_history.py`](../../../.cursor/foundry/cli/foundry_cli/operator_history.py) |
| TUI layout & wait panel | [`tui/app.py`](../../../.cursor/foundry/cli/foundry_cli/tui/app.py), [`test_tui.py`](../../../.cursor/foundry/cli/tests/unit/test_tui.py) (`#advance-btn` not mounted) |
| Engine tests | [`test_rel011_blocked_intake_recovery.py`](../../../.cursor/foundry/cli/tests/unit/test_rel011_blocked_intake_recovery.py), [`test_rel005_loop_history.py`](../../../.cursor/foundry/cli/tests/unit/test_rel005_loop_history.py) |
| Related spec | [cli-operator-ux/spec.md](../cli-operator-ux/spec.md) D14–D15 |
| Run evaluation | **evaluate-run not run—engine verdict omitted.** |
