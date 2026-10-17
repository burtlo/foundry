# Run block visibility — implementation map

Status: **ready for orchestration** — companion to [spec.md](spec.md) (approved 2026-10-16). Canonical map for implementer assignment and verifier checklists. Refresh with `/spec-implementation-map @spec.md` after material spec or code changes.

## Spec alignment

### Strengths (spec)

- D1–D12 and AC 1–11 name one projection, the surfaces that render it, and the commands that may appear. Out of scope excludes engine park rules, new halt codes, and a diagnostics pane.
- Lawful commands are listed as exact lines (`foundry run advance --run <id>`, `foundry retry <id>`, `foundry answer <id>`, `foundry decide <id> <option>`, `foundry start <id>`).
- The card reads stored message, code, and findings. It does not re-run validation.
- Short status labels and the technical-context toggle stay as they are. The change is the last feed entry, the removed wait panel, and Needs **—** for an agent wait.

### Strengths (repository)

- `status_reason` is already on the snapshot and on `run.get` JSON (`code`, `message`, `retry_eligible`) via [run_status_reason.py](../../../.cursor/foundry/cli/foundry_cli/engine/run_status_reason.py) and [get_run](../../../.cursor/foundry/cli/foundry_cli/run_service.py). Human status simply does not print it.
- Blocked execute and verify intake already seal `receipts/assessment.md` with a `## Findings` bullet list, then store a joined message on `status_reason` ([blocked_intake.py](../../../.cursor/foundry/cli/foundry_cli/engine/blocked_intake.py), [intake_executor.py](../../../.cursor/foundry/cli/foundry_cli/engine/intake_executor.py) `_write_assessment`).
- Repair and reverify limits already set `REPAIR_LIMIT_EXCEEDED` / `REVERIFY_LIMIT_EXCEEDED` with `retry_eligible: true` ([lifecycle.py](../../../.cursor/foundry/cli/foundry_cli/engine/lifecycle.py)). [test_rel005_loop_history.py](../../../.cursor/foundry/cli/tests/unit/test_rel005_loop_history.py) covers that payload.
- Step titles and short status words already exist: [run_labels.py](../../../.cursor/foundry/cli/foundry_cli/run_labels.py) `node_step_title` and `run_status_label` (`Running`, `Halted`, `Execution error`, `Definition error`, `Paused`, `Completed`).
- Operator history is a pure section list rendered to markdown ([operator_history.py](../../../.cursor/foundry/cli/foundry_cli/operator_history.py)), served by `run.operator_history`, and shown in `#context-markdown`.
- Gate options, question fields, and execute-start already have TUI handlers and host RPCs (`run.decide`, `run.answer`, `run.start`, `run.advance`, `run.retry`). Execute-start already offers start and does not offer gate options.
- The technical-context toggle already keeps the steward packet off until opened.

### Gaps and clarifications before build

| Topic | Present state | Spec requirement | Suggested resolution |
|-------|---------------|------------------|----------------------|
| When `foundry run advance` is lawful | `advance_run` returns ok even when it does not progress (`terminal_status` or an existing wait). There is no `advance_eligible` flag. `paused` is not in `TERMINAL_RUN_STATUSES`, but auto-advance and the operator smoke skip it. Blocked intake is an `operator` wait recovered by advance. Repair-limit pause and halt are recovered by retry. | Print `foundry run advance --run <id>` only when advance is legal, and omit any command the engine would not treat as the transition. | Do not call advance to probe. Print the advance line only when status is not in `TERMINAL_RUN_STATUSES` (`completed`, `halted`, `execution_error`, `definition_error`), status is not `paused`, and `wait.kind` is `operator`. Decision, question, agent, halt, and pause do not get an advance line. |
| Findings vs message | Blocked-intake `status_reason.message` is the findings joined with `"; "`. The bullet list lives in the sealed assessment. Repair-limit halts have a message and code and usually no assessment. `intake_validation_findings` re-runs validation. | Status and the card show the human message and each finding already stored. Do not re-validate. | Message is `status_reason.message` when set, otherwise `wait.summary`. Findings are the `-` bullets under `## Findings` in the sealed assessment for the active visit, read from disk. If that file is absent, the findings list is empty. Print both even when the message repeats the bullets. |
| Decide lines | Gate options live on the node as `produces.options` (for example `accept` / `reject` on `shape.present.gate`). The TUI falls back to `accept` and `reject` when context options are empty. | One `foundry decide <id> <option>` line per lawful option. Execute-start does not print decide lines. | One shared option list for status lines and TUI buttons: node `produces.options`, then the existing accept/reject fallback when that list is empty. One status line per option. No literal `<option>` placeholder. |
| Non-parked status | Human status is one identity line plus an optional `wait=` line. | Full explanation is for a halt or a person-wait. An agent wait has no card. | When the projection is null (running with no person-wait, agent wait, completed), keep today's status lines. Do not print an empty command block. |
| JSON shape | `run.get` already returns `status_reason`, `wait`, and `halt_reason`. It does not return step title, findings, or command lines. Host `run.get` is `get_run`, which does not load the flow. | JSON may gain fields for this same projection. `status_reason` stays the source. `foundry runs` and `run.list` stay short. | Add optional `parked` (or JSON null) on `run.get` only: heading, step title, node id, reason code, message, findings, command lines. `get_run` takes the registry bundle from the host handler and from `cmd_status`. Leave `run.list` unchanged. |
| Needs **Agent** | `needs_label("agent")` returns **Agent**. [test_tui.py](../../../.cursor/foundry/cli/tests/unit/test_tui.py) asserts that on the helper, the run index, and the header. cli-operator-ux D17 / AC 25 shipped that word. | D10 / AC 8: agent wait and no wait are **—**. | This spec replaces the agent cell only. Change the map in `needs_label`. Do not change `wait_kind` on the host payload. Leave the older bundle's spec as history. |
| Card vs steward packet | Scroll order is history, `#wait-panel`, hidden `#technical-markdown`. | The card is the last operator-history entry. The toggle still reveals the steward packet and stays off until opened. | Append a `parked` history section. Mount action widgets after `#context-markdown`. Remove `#wait-panel`. Keep technical markdown after the actions, still hidden until the toggle. |

### Acceptance criteria traceability

| AC | Present | Delta / work |
|----|---------|----------------|
| 1 | JSON has node id, `status_reason`, and `wait`. Human status prints neither step title, reason code, message, nor findings. | **P1** builds that record from the snapshot and the sealed assessment. **P2** prints it. |
| 2 | No command hints. Retry, decide, answer, and start exist as commands. Advance has no legality predicate. | **P1** emits the five command forms under the predicate in the gaps table. **P2** prints one line each, in that order. |
| 3 | A halt with no retry still omits the explanation. | **P1** returns the explanation with an empty command list. **P2** prints no hint line. |
| 4 | History sections stop at intake, model response, questions, decisions, and approval material. The wait panel is a separate widget. | **P3** appends the parked section last. **P5** removes `#wait-panel`. |
| 5 | Decision, question, and execute-start controls sit in `#wait-panel`. Advance is a key binding with no button. Retry has a host method and no TUI client. Operator waits get an empty panel. | **P5** mounts those controls, **Advance**, and **Retry** after the history markdown, using the **P1** command list. |
| 6 | Execute-start already returns only the start button. | **P5** keeps that branch inside the action area. **P1** emits `foundry start <id>` and no decide lines. |
| 7 | Index and header already use `run_status_label`. Findings are not on those surfaces. `foundry runs` is a raw token line and stays that way. | No new index copy. **P5** must not put findings in the header. |
| 8 | Operator, decision, and question labels match. Agent is **Agent**. Empty wait is already **—**. | **P4** maps `agent` to **—** in `needs_label`, which the index and header both call. |
| 9 | An agent wait still renders history and an empty wait panel. | **P1** returns null for `wait.kind == agent`. **P3** adds no section. **P5** mounts no action widgets. |
| 10 | Toggle and `#technical-markdown` already behave this way. | **P5** leaves that path in place, still after the card. |
| 11 | The three parks store different codes and messages. Nothing projects them through one card. | **P1** one record. **P2** and **P3** render it. Fixtures from the existing blocked-intake and repair-limit tests. |

---

## Repository layout

Porcelain, history, and the TUI already share snapshot fields. They do not share a parked-run view. The new helper sits beside operator history and is called from status and from history. The TUI stops owning a separate wait panel and reads the same command list.

| Role | Path |
|------|------|
| Human status formatter | [foundry.py](../../../.cursor/foundry/cli/foundry.py) `_format_status` |
| Status command | [user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py) `cmd_status` |
| `run.get` payload | [run_service.py](../../../.cursor/foundry/cli/foundry_cli/run_service.py) `get_run`; host [handlers.py](../../../.cursor/foundry/cli/foundry_cli/host/handlers.py) `run_get` |
| Reason payload | [run_status_reason.py](../../../.cursor/foundry/cli/foundry_cli/engine/run_status_reason.py) |
| Blocked intake message | [blocked_intake.py](../../../.cursor/foundry/cli/foundry_cli/engine/blocked_intake.py) |
| Assessment bullets | [intake_executor.py](../../../.cursor/foundry/cli/foundry_cli/engine/intake_executor.py) `_write_assessment` |
| Labels | [run_labels.py](../../../.cursor/foundry/cli/foundry_cli/run_labels.py) |
| Operator history | [operator_history.py](../../../.cursor/foundry/cli/foundry_cli/operator_history.py), [operator_history_service.py](../../../.cursor/foundry/cli/foundry_cli/operator_history_service.py) |
| TUI layout and waits | [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) |
| TUI host calls | [tui/host_client.py](../../../.cursor/foundry/cli/foundry_cli/tui/host_client.py) |
| Gate options in context | [context.py](../../../.cursor/foundry/cli/foundry_cli/context.py) `_produces_block` |
| Retry RPC | [operator.py](../../../.cursor/foundry/cli/foundry_cli/engine/operator.py) `retry_run`; host `run.retry` |
| Tests | [test_tui.py](../../../.cursor/foundry/cli/tests/unit/test_tui.py), [test_operator_history.py](../../../.cursor/foundry/cli/tests/unit/test_operator_history.py), [test_rel005_loop_history.py](../../../.cursor/foundry/cli/tests/unit/test_rel005_loop_history.py), [test_rel011_blocked_intake_recovery.py](../../../.cursor/foundry/cli/tests/unit/test_rel011_blocked_intake_recovery.py) |

---

## Workstreams mapped to decisions

### D1, D5, D9, D11 — one parked projection

**Present:** `cmd_status` returns `status_reason` and `wait` in JSON. `_format_status` prints run id, phase, status, node, revision, and sometimes `wait=<kind> summary='…'`. Findings are on the sealed assessment, not on that payload. Nothing lists a next command.

**Required:** For a halt or a person-wait, status includes step title, node id, reason code when set, message, each stored finding, then one line per lawful command. The same record feeds history and the TUI. Agent waits, idle runs, and completed runs do not get it.

| Resource | Role |
|----------|------|
| New helper beside [operator_history.py](../../../.cursor/foundry/cli/foundry_cli/operator_history.py) | Pure projection. Null when not parked. |
| [run_labels.py](../../../.cursor/foundry/cli/foundry_cli/run_labels.py) | Step title and the halt heading. |
| [run_status_reason.py](../../../.cursor/foundry/cli/foundry_cli/engine/run_status_reason.py) | Code, message, `retry_eligible`. Do not recompute eligibility. |
| Sealed `assessment.md` | Finding bullets. Do not call `intake_validation_findings`. |

**Risks:** Calling advance to discover legality would mutate a run. The predicate in the gaps table is the rule.

### D3, D4, D8, D12 — last feed entry and actions

**Present:** `build_operator_history_sections` never emits a parked section. `RunDetailScreen` mounts `#wait-panel` only for `decision`, `user_input`, and `execute.start`. Operator waits leave it empty. `#advance-btn` is handled and not mounted. `HostClient` has no retry method.

**Required:** The explanation is the last history section. Its heading is the Needs word for a person-wait and the short status word for a halt with no wait. Action widgets sit in that same scroll. The wait panel is gone. Execute-start still offers only start.

| Resource | Role |
|----------|------|
| [operator_history.py](../../../.cursor/foundry/cli/foundry_cli/operator_history.py) | New last section. Heading is dynamic, so it cannot be a single static map entry unless the section carries its own heading. |
| [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) | Drop `#wait-panel`. Mount the existing controls plus Advance and Retry after `#context-markdown`. |
| [tui/host_client.py](../../../.cursor/foundry/cli/foundry_cli/tui/host_client.py) | Add `retry` → `run.retry`. |

**Risks:** Many TUI tests query `#wait-panel`. They move with the widget. The `a` advance binding stays.

### D6, D7, D10 — index, header, Needs

**Present:** Index columns are Run ID, Status, Current step, Needs. Status uses the short labels. Needs maps `operator` → Action, `decision` → Approval, `user_input` → Answers, `agent` → Agent, empty → **—**.

**Required:** Status labels stay. Findings stay off the index and header. Agent Needs becomes **—**.

| Resource | Role |
|----------|------|
| [run_labels.py](../../../.cursor/foundry/cli/foundry_cli/run_labels.py) `needs_label` | One map change covers the index and the header. |
| [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py) `_update_summary` and the run list | Already call `needs_label` and `run_status_label`. |

**Risks:** cli-operator-ux tests and AC 25 still expect **Agent**. Update the tests in this bundle's package. Do not change host `wait_kind`.

### D2 — bundle

No code. The map lives at `docs/plans/run-block-visibility/implementation.md`.

---

## Orchestration packages

| ID | Title | Surfaces | Depends on | Primary paths | Verify (AC / tests) |
|----|-------|----------|------------|---------------|---------------------|
| P1 | Parked-run projection | code | — | New helper next to `operator_history.py`; reads `run_status_reason`, `run_labels`, sealed assessment | AC 1–3, 6, 9, 11; new unit test |
| P2 | Human `foundry status` | cli-ui, code | P1 | `foundry.py` `_format_status`; `get_run`; host `run_get`; `cmd_status` | AC 1–3, 11; formatter unit test |
| P3 | Operator-history parked section | code, host-ui | P1 | `operator_history.py` | AC 4, 9, 11; `test_operator_history.py` |
| P4 | Needs **—** for agent | cli-ui, host-ui | — | `run_labels.py`; `test_tui.py` label assertions | AC 8 |
| P5 | TUI card actions, no wait panel | host-ui | P2, P3, P4 | `tui/app.py`; `tui/host_client.py` | AC 4–7, 9, 10; `test_tui.py` |

### Package briefs (for implementer agents)

#### P1 — Parked-run projection

- **Goal:** One pure function that returns null or the parked record.
- **Deliverables:** A helper that takes the snapshot, flow, and run directory. It returns null for an agent wait, a running run with no person-wait, and a completed run. Otherwise it returns heading, step title, node id, reason code (only when set), message, findings, and command lines. Advance, retry, answer, decide, and start follow the gaps-table predicate, in that order. Decide is one line per option. Execute-start emits only `foundry start <id>`. Findings are read from the sealed assessment, not recomputed. Unit tests cover blocked execute intake (advance, findings), repair-limit pause or halt (retry, no advance), blocked verify intake (same card shape), a gate, a question wait, execute-start, an agent wait (null), an idle run (null), and a halt with no legal command (explanation, empty commands).
- **Out of scope:** Printing, history markdown, TUI widgets, engine park rules, `run.list`.
- **Touchpoints:** New module; [run_status_reason.py](../../../.cursor/foundry/cli/foundry_cli/engine/run_status_reason.py); [run_labels.py](../../../.cursor/foundry/cli/foundry_cli/run_labels.py); assessment written by [intake_executor.py](../../../.cursor/foundry/cli/foundry_cli/engine/intake_executor.py). Node id for execute-start is `execute.start`.

#### P2 — Human `foundry status`

- **Goal:** `foundry status <run>` prints the P1 record, and `run.get` carries it.
- **Deliverables:** `get_run` accepts the registry bundle and adds `parked` (object or null) without removing `status_reason`. Host `run_get` passes `self.bundle`. Local `cmd_status` passes the command bundle. `_format_status` prints step title, node id, reason code when set, message, each finding, then the command lines. When `parked` is null, keep the current identity line and optional wait line. `foundry runs` stays as it is.
- **Out of scope:** History sections, TUI, Needs labels.
- **Touchpoints:** [foundry.py](../../../.cursor/foundry/cli/foundry.py), [run_service.py](../../../.cursor/foundry/cli/foundry_cli/run_service.py), [user_cli.py](../../../.cursor/foundry/cli/foundry_cli/user_cli.py), [handlers.py](../../../.cursor/foundry/cli/foundry_cli/host/handlers.py).

#### P3 — Operator-history parked section

- **Goal:** The explanation is the last operator-history section, using the same words as status.
- **Deliverables:** `build_operator_history_sections` appends a section when P1 is non-null. The heading is the P1 heading (Action, Approval, Answers, or the short status word). The body includes step title, node id, reason code, message, and findings, untruncated. Agent and idle runs gain no section. Existing sections stay in their current order ahead of this one.
- **Out of scope:** Buttons, status porcelain, Needs.
- **Touchpoints:** [operator_history.py](../../../.cursor/foundry/cli/foundry_cli/operator_history.py). The service and host method stay as they are; they already render whatever sections the builder returns.

#### P4 — Needs **—** for agent

- **Goal:** An agent wait and a run with no wait both show Needs **—**.
- **Deliverables:** `needs_label("agent")` returns **—**. Action, Approval, and Answers stay. Update the three `test_tui.py` assertions that expect **Agent**.
- **Out of scope:** The parked card, status text, host `wait_kind`.
- **Touchpoints:** [run_labels.py](../../../.cursor/foundry/cli/foundry_cli/run_labels.py), [test_tui.py](../../../.cursor/foundry/cli/tests/unit/test_tui.py).

#### P5 — TUI card actions, no wait panel

- **Goal:** The last scroll entry explains the park and holds the controls. The wait panel is gone.
- **Deliverables:** Remove `#wait-panel`. After `#context-markdown`, mount gate buttons, question fields and submit, the execute-start button, **Advance** when the advance command is present, and **Retry** when the retry command is present. Execute-start still does not mount gate options. No action widgets when `parked` is null. `HostClient.retry` calls `run.retry`. Keep the `a` binding and the technical-context toggle. Header and index still use short status labels and do not list findings. Update TUI tests that query `#wait-panel` or assert that Advance is absent.
- **Out of scope:** Rewriting operator-history section kinds, changing steward markdown, adding a side pane.
- **Touchpoints:** [tui/app.py](../../../.cursor/foundry/cli/foundry_cli/tui/app.py), [tui/host_client.py](../../../.cursor/foundry/cli/foundry_cli/tui/host_client.py). Read `parked.commands` from `run.get` so the buttons match status.

### Verifier briefs

#### P1 — verification

- **Must prove:** Blocked execute intake yields step title, node id, `INTAKE_BLOCKED`, the stored message, each assessment bullet, and only `foundry run advance --run <id>`. Repair-limit yields the code, message, `foundry retry <id>`, and no advance line. Verify intake uses the same record shape with its own message and findings. A gate yields one decide line per option and no start line. Execute-start yields only `foundry start <id>`. A question wait yields `foundry answer <id>`. A halt with no legal transition yields the explanation and an empty command list. Agent, idle, and completed return null. The helper does not call intake validation.
- **Commands / probes:** New unit test under `.cursor/foundry/cli/tests/unit/`. Build snapshots in the style of `test_rel005_loop_history.py` and `test_rel011_blocked_intake_recovery.py`, including a sealed assessment file.
- **Regression watch:** `retry_eligible` still comes only from `RETRY_ELIGIBLE_HALT_CODES`. `INTAKE_BLOCKED` stays ineligible.

#### P2 — verification

- **Must prove:** Human status for the three parks matches the P1 record and ends with the command lines. A no-command halt prints the explanation and nothing that looks like a command hint. An agent wait and an idle run still print the current short status. JSON `status_reason` remains. `parked` is present on host and local `run.get`. `run.list` shape is unchanged.
- **Commands / probes:** Unit test that calls the formatter and `get_run` with a bundle. Existing `test_rel005_loop_history.py` status payload assertions still pass.
- **Regression watch:** `foundry runs` output. Shape-command status hints (`foundry status <id>`) stay one-line hints, not the parked essay.

#### P3 — verification

- **Must prove:** History markdown for a person-wait or halt ends with the P1 heading and body. An agent-wait fixture used by `test_operator_history.py` gains no parked heading. Section order ahead of the card is unchanged.
- **Commands / probes:** Extend `test_operator_history.py`.
- **Regression watch:** Intake, model response, questions, decisions, and approval-material sections still render.

#### P4 — verification

- **Must prove:** `needs_label("agent")` is **—**. User-input, decision, operator, empty, and unknown kinds are unchanged. The run-list row and the run-view header show **—** for an agent wait.
- **Commands / probes:** `test_tui.py` label and header tests.
- **Regression watch:** Do not rename **Action**, **Approval**, or **Answers**.

#### P5 — verification

- **Must prove:** For a blocked intake, a repair-limit halt, and a blocked verify intake, the last history text matches status, and **Advance** or **Retry** is mounted only when that command was printed. A gate, a question wait, and execute-start show their controls in the scroll, with no `#wait-panel`. Execute-start has no gate buttons. An executing agent has no parked card and Needs **—**. The index still shows short status labels for an `execution_error` run and a halted run, without findings. The technical-context toggle still reveals the steward packet and stays off until opened.
- **Commands / probes:** `test_tui.py` with Textual `run_test`. Mock `run.get` so `parked.commands` is set, and mock operator-history markdown so the explanation is the last section.
- **Regression watch:** Decide, answer, and start still submit through the existing handlers. The `a` binding still advances. Opening technical context does not replace the card.

---

## Suggested implementation order

**Canonical package sequence:** P1 → P2 → P3 → P4 → P5

P2, P3, and P4 may proceed in parallel after P1. P4 does not depend on P1, but it should land before P5 so the header assertions and the card tests are not edited in two overlapping passes. P5 waits until `run.get` exposes `parked.commands` and history exposes the explanation.

### Build order rationale

Status and the main feed must show the same explanation. That forces the projection to exist before either surface. The TUI action area is the only package that deletes `#wait-panel`, and it needs both the command list and the history text, so it is last. Needs is a one-function label change on a different surface and does not block status or history.

1. P1 defines the record and the command predicate once.
2. P2 prints it from `foundry status` and attaches it to `run.get`.
3. P3 appends the same words as the last history section.
4. P4 changes the agent Needs cell.
5. P5 moves controls into the scroll and removes the wait panel.

---

## Test and fixture resources

| Asset | Use |
|-------|-----|
| [test_rel011_blocked_intake_recovery.py](../../../.cursor/foundry/cli/tests/unit/test_rel011_blocked_intake_recovery.py) | Blocked execute intake snapshot and recovery via advance |
| [test_rel005_loop_history.py](../../../.cursor/foundry/cli/tests/unit/test_rel005_loop_history.py) | Repair-limit pause and reverify halt with `retry_eligible` |
| [test_operator_history.py](../../../.cursor/foundry/cli/tests/unit/test_operator_history.py) | Section order; extend for the parked section |
| [test_tui.py](../../../.cursor/foundry/cli/tests/unit/test_tui.py) | Needs labels, wait panel, header, technical-context toggle |
| Verify intake writer | [verify_step_executor.py](../../../.cursor/foundry/cli/foundry_cli/engine/verify_step_executor.py) seals the same assessment shape as execute intake |

**CI:** These are pytest unit tests plus Textual `run_test`. They do not need a live host, credentials, or a platform split. Run them from `.cursor/foundry/cli`.

---

## Cross-cutting risks summary

| Risk | Severity | Mitigation |
|------|----------|------------|
| Advance has no engine predicate, and `paused` is not terminal | High | Use the gaps-table rule. Never call advance from the projection. |
| Host `run.get` omits findings unless `get_run` loads the bundle | High | P2 passes the bundle from the host handler and from `cmd_status`. |
| Reading findings by re-running validation | Medium | Parse the sealed assessment only. |
| `#wait-panel` removal breaks TUI tests | Medium | P5 updates those tests in the same change. |
| cli-operator-ux still documents Needs **Agent** | Low | This spec wins for that cell. Update tests. Do not edit the other bundle unless asked. |
| Message text repeats finding bullets for blocked intake | Low | Print both, as AC 1 requires. |

---

## Related artifacts

- [spec.md](spec.md)
- [retro.md](retro.md)
- [cli-operator-ux/spec.md](../cli-operator-ux/spec.md) D14–D15 and D17 (agent Needs superseded here)
