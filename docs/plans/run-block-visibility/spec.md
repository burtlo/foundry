# Run block visibility

Status: **approved specification** — from operator retro interview (2026-10-16).

## Source

- Bundle: [README](README.md)
- Retro: [retro.md](retro.md) — investigations: “Blocked does not explain what failed (any node)”; “Validation and intake issues are computed but not in the operator feed”; “TUI: no main-feed block card”; “Operator wait Action without checklist”

## Operator outcome

When a run is halted or waiting on a person, the operator can read what happened and the lawful next command from `foundry status <run>`, and can see the same explanation and act on it as the last entry in the TUI run view, without opening the run directory or the host log.

## Problem statement

Parked runs already store a typed reason, a human message, and often a findings list. Human status omits that reason. The TUI run index and header show a short status and a Needs word, and the main feed does not carry the explanation. The wait panel covers gates, questions, and execute-start authorization, and it stays empty for operator waits and halts. Operators then open receipts, assessments, or logs to decide whether to advance, retry, decide, answer, or start.

## Scope

### In scope

- One generic parked-run card for every halt and every wait on a person (`operator`, `decision`, `user_input`, including execute-start authorization), on any node.
- The card is the last entry in the main feed (operator history). It contains the explanation and the action area.
- The separate wait panel is removed. Question fields, gate options, execute-start authorization, **Advance**, and **Retry** render inside that last entry.
- `foundry status <run>` prints the same full explanation and each lawful next command.
- Run index and run-view header keep today’s short status labels (`Running`, `Halted`, `Execution error`, `Definition error`, `Paused`, `Completed`).
- Needs stays **Action**, **Approval**, and **Answers** for those waits. An in-progress agent wait and an idle run show **—**.

### Out of scope

- Engine rules for when a run parks, and any new halt codes.
- A side or extra diagnostics panel. Steward detail stays behind the existing technical-context toggle.
- A `status --diagnose` command, and failing earlier at `start`, as the way to explain a park.
- Per-reason copy templates, and per-code strings on the run index.
- Rewriting the shipped operator-history and attach work, except for the card, the removed wait panel, and the Needs change for agent waits.
- Full explanation text on `foundry runs` or the TUI run index.
- A card while an agent is executing.
- Run-correctness review. No run id was attached to the retro.

## Decisions

| ID | Decision | Rationale | Retro link |
|----|----------|-----------|------------|
| D1 | Ship the full card in one spec: human `status`, operator history, and TUI actions. | The operator needs the reason and the next action on the surfaces they already have open. | Cross-cutting “one parked run projection” |
| D2 | Spec lives in `docs/plans/run-block-visibility/`. | Keeps the cross-node block story in this bundle. | Cross-cutting bundle relationship |
| D3 | The card is the last entry in the main feed. No new panel. | A restored right-hand pane costs width. The existing technical-context toggle remains the steward packet. | “Main feed vs side panel” |
| D4 | Every person-wait and halt uses that one last entry. The wait panel is removed. | Gate, question, start, and blocked-step UI should be one place. | TUI wait-panel investigation |
| D5 | One generic card: step, reason code, message, findings, lawful actions. | Node-specific detail is already in the message and the sealed findings. | “Action without checklist” |
| D6 | Index and header status stay the current short labels. The body and `foundry status` hold the full explanation. | The index stays scannable. | “Blocked does not explain what failed” |
| D7 | Needs stays **Action**, **Approval**, and **Answers**. **Attention** is not introduced. | Those words mark different waits. | Operator-wait investigation |
| D8 | Existing interactions move into the card’s action area. | Removing the wait panel must keep the controls. | “Actions beside explanation” |
| D9 | `foundry status <run>` prints the full explanation. | Operators who stay on the CLI can see the failure without the run directory. | Status porcelain gap |
| D10 | An agent wait shows Needs **—**, as does a run with no wait. | The operator is not being asked to act while the agent runs. | Run-list Needs labels |
| D11 | `foundry status <run>` also prints each lawful next command. | Status should name the next command as well as the failure. | Probe: name the fix and the next command |
| D12 | The card heading is the Needs word when a person is waiting, and the short status word when the run is halted with no wait. | The heading matches the index vocabulary; the body carries the detail. | Interview assumption, uncontradicted |

## Assumptions

- Findings are read from the sealed assessment or blocked receipt. The card does not re-run validation.
- A control or command is included only when the engine already allows that transition. Ineligible actions are omitted.
- `foundry status` and the TUI last entry show the same explanation.
- The explanation is complete. It is not truncated.
- `foundry runs` stays a short listing.
- JSON may gain fields only to carry this same projection. Existing `status_reason` data remains the source.

## Acceptance criteria

1. For a halted run or a person-wait, `foundry status <run>` includes the active step title, the node id, the reason code when one is set, the human message, and each finding already stored on the sealed artifact.
2. That status output ends with one line per lawful command, and no line for a command the engine rejects:
   - `foundry run advance --run <id>` when advance is legal
   - `foundry retry <id>` when `retry_eligible` is true
   - `foundry answer <id>` when `wait.kind` is `user_input`
   - `foundry decide <id> <option>` when `wait.kind` is `decision` and the node is not execute start
   - `foundry start <id>` when the wait is execute-start authorization
3. When no transition is legal, status still prints the explanation and prints no command hint.
4. The TUI run view shows that same explanation as the last entry in the main scroll. The separate wait panel is gone.
5. That last entry hosts the action area: gate option controls, clarifying-question fields and submit, the execute-start authorization control, **Advance** when advance is legal, and **Retry** when `retry_eligible` is true.
6. Execute-start authorization offers start, and does not offer gate options.
7. The run index and the run-view header keep the current short status labels and do not show the findings list.
8. Needs is **Action** for `operator`, **Approval** for `decision`, **Answers** for `user_input`, and **—** for an agent wait and for no wait.
9. While an agent is executing, the run view has no parked card.
10. The technical-context toggle still reveals the steward packet and stays off until the operator opens it.
11. A blocked intake, a repair-limit halt, and a verify-intake block all use this same card. The copy differs only by the stored message, code, and findings.

## Verification plan

- Park a run on blocked execute intake, a repair-limit halt, and a blocked verify intake. From `foundry status` alone, read the findings and the printed command. Open the same runs in the TUI and confirm the last entry matches, including **Advance** or **Retry** only when that command was printed.
- Open a gate wait, a clarifying-question wait, and execute-start. Confirm the controls sit in the last entry, the wait panel is absent, and status prints `decide`, `answer`, or `start` respectively.
- Open a run whose agent is executing, and a run that is idle. Confirm Needs is **—** and the executing run has no parked card.
- Confirm the run index still shows short status labels for an `execution_error` run and a halted run.

## Implementation hints (optional)

- One projection helper over the active node, `wait`, `status`, `status_reason`, and sealed findings. Human status and operator history both render it.
- TUI: mount the action widgets at the end of the main scroll and stop mounting the wait panel. The existing `a` advance binding can stay.
- Needs: `run_labels.needs_label` returns **—** for `agent`.
- Touchpoints named in the retro: `foundry._format_status`, `operator_history.py`, `render.py`, `tui/app.py`, `run_status_reason.py`, `blocked_intake.py`.

## Deferred / follow-up

- A side diagnostics pane.
- A runbook table of halt codes.
- `status --diagnose`, and pre-start checks that would stop a run from parking later.
- Operator time-to-fix probes from the retro.
