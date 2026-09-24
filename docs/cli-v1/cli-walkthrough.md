# Flow walkthrough

Status: **draft capability spec**

Narrative for flow `implementation` in `.cursor/foundry/flows/factory-flow.yaml`. Visit ids are placeholders (`v-001`, …). A fresh run starts at `shape.intake`. The engine admits each visit, runs hooks, opens steward work, and routes on seal.

Unless noted, each step ends with [foundry visit transition](cli-visit.md) (capability `transition`) after artifacts and receipts are linked. User gates use [foundry gate decide](cli-gate.md). Engine gates record `gate.resolved` inside the engine.

**Hub:** [cli.md](cli.md) — conventions, command index, open questions.

**Ledger inspection:** [cli-ledger.md](cli-ledger.md) — every ledger block below is what you would see from `foundry ledger show` (text is the default terminal format; add `--json` for the envelope in [cli-ledger.md](cli-ledger.md)).

**Run id in examples:** `porcelain-0007`

---

## Happy path

### Phase: shape

#### v-001 — `shape.intake`

Steward runs shape parent; engine admits visit.

| Actor | Command |
|---|---|
| Engine | `foundry run create --flow implementation --json` |
| Steward | `foundry app validate --workspace .` |
| Steward | `foundry artifact publish ticket --source run:ticket.json` |
| Steward | `foundry receipt seal --schema registry:schemas/intake-receipt.schema.json --file run:receipts/intake.json` |
| Steward | `foundry receipt seal --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json` |
| Steward | `foundry visit transition --summary "Intake complete"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-run.md](cli-run.md) | `run create` |
| [cli-app.md](cli-app.md) | `app validate` |
| [cli-artifact.md](cli-artifact.md) | `artifact publish` |
| [cli-receipt.md](cli-receipt.md) | `receipt seal` |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-check.md](cli-check.md) | engine hooks: `reshape-within-limit`, `validate-manifest`, `intake-receipt-sealed` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` (audit) |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 1 --to-seq 24

seq  at                        visit  node          type               detail
───  ────────────────────────  ─────  ────────────  ─────────────────  ─────────────────────────────────────────────
  1  2026-09-24T14:00:00Z      —      —             run.status_changed running ← (new)
  2  2026-09-24T14:00:00Z      v-001  shape.intake  visit.admitted     source: entry
  3  2026-09-24T14:00:00Z      v-001  shape.intake  lifecycle.changed  admitted → examined
  4  2026-09-24T14:00:00Z      v-001  shape.intake  check.recorded     on_examine: reshape-within-limit → pass
  5  2026-09-24T14:00:00Z      v-001  shape.intake  policy.applied     reshape-within-limit → continue
  6  2026-09-24T14:00:01Z      v-001  shape.intake  check.recorded     on_open: validate-manifest → pass
  7  2026-09-24T14:00:01Z      v-001  shape.intake  policy.applied     validate-manifest → continue
  8  2026-09-24T14:00:01Z      v-001  shape.intake  lifecycle.changed  examined → opened
  9  2026-09-24T14:02:10Z      v-001  shape.intake  artifact.linked    ticket → run:ticket.json
 10  2026-09-24T14:03:05Z      v-001  shape.intake  receipt.linked     intake-receipt.schema.json
 11  2026-09-24T14:03:06Z      v-001  shape.intake  receipt.linked     agent-receipt.schema.json
 12  2026-09-24T14:03:30Z      v-001  shape.intake  check.recorded     on_close: (step checks) → pass
 13  2026-09-24T14:03:30Z      v-001  shape.intake  policy.applied     on_close → continue
 14  2026-09-24T14:03:30Z      v-001  shape.intake  lifecycle.changed  opened → closed
 15  2026-09-24T14:03:31Z      v-001  shape.intake  check.recorded     on_seal: intake-receipt-sealed → pass
 16  2026-09-24T14:03:31Z      v-001  shape.intake  policy.applied     intake-receipt-sealed → continue
 17  2026-09-24T14:03:31Z      v-001  shape.intake  lifecycle.changed  closed → sealed
 18  2026-09-24T14:03:31Z      v-001  shape.intake  visit.sealed       outcome: completed
 19  2026-09-24T14:03:31Z      v-001  shape.intake  connection.taken   shape.intake-to-shape.examine → shape.examine
 20  2026-09-24T14:03:31Z      v-002  shape.examine visit.admitted     source: v-001 / shape.intake-to-shape.examine
```

**Gate decisions:** none (step).

**Route:** `shape.intake-to-shape.examine` → `shape.examine`.

#### v-002 — `shape.examine`

Conversational examination; no declared artifacts.

| Actor | Command |
|---|---|
| Steward | (user Q&A via `allow.user.ask`; state updates via steward tools) |
| Steward | `foundry receipt seal --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json` |
| Steward | `foundry visit transition --summary "Examination round complete"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-receipt.md](cli-receipt.md) | `receipt seal` |
| [cli-visit.md](cli-visit.md) | `visit transition`, `visit state patch` (steward tools) |
| [cli-check.md](cli-check.md) | engine hooks: `prior-shape-intake-sealed`, `agent-receipt-sealed` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 20 --to-seq 35

seq  at                        visit  node          type               detail
───  ────────────────────────  ─────  ────────────  ─────────────────  ─────────────────────────────────────────────
 20  2026-09-24T14:03:31Z      v-002  shape.examine visit.admitted     source: v-001 / shape.intake-to-shape.examine
 21  2026-09-24T14:03:31Z      v-002  shape.examine lifecycle.changed  admitted → examined
 22  2026-09-24T14:03:31Z      v-002  shape.examine check.recorded     on_examine: prior-shape-intake-sealed → pass
 23  2026-09-24T14:03:31Z      v-002  shape.examine policy.applied     prior-shape-intake-sealed → continue
 24  2026-09-24T14:03:32Z      v-002  shape.examine lifecycle.changed  examined → opened
 25  2026-09-24T14:18:00Z      v-002  shape.examine receipt.linked     agent-receipt.schema.json
 26  2026-09-24T14:18:20Z      v-002  shape.examine lifecycle.changed  opened → closed
 27  2026-09-24T14:18:21Z      v-002  shape.examine check.recorded     on_seal: agent-receipt-sealed → pass
 28  2026-09-24T14:18:21Z      v-002  shape.examine policy.applied     agent-receipt-sealed → continue
 29  2026-09-24T14:18:21Z      v-002  shape.examine lifecycle.changed  closed → sealed
 30  2026-09-24T14:18:21Z      v-002  shape.examine visit.sealed       outcome: completed
 31  2026-09-24T14:18:21Z      v-002  shape.examine connection.taken   shape.examine-to-shape.present → shape.present
 32  2026-09-24T14:18:21Z      v-003  shape.present visit.admitted     source: v-002 / shape.examine-to-shape.present
```

**Fast lane:** when `state.open_clarifying_questions_count == 0`, connection `shape.examine-to-shape.present` is eligible — **`shape.examine.gate` is skipped**. When count ≠ 0, route is `shape.examine-to-shape.examine.gate` instead (see [rework section](#shapeexamine-gate-when-open-questions--0)).

Happy path assumes fast lane (zero open questions).

**Route:** `shape.examine-to-shape.present` → `shape.present`.

#### v-003 — `shape.present`

| Actor | Command |
|---|---|
| Steward | `foundry artifact publish presentation --source run:artifacts/v-003/presentation.md` |
| Steward | `foundry receipt seal --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json` |
| Steward | `foundry visit transition --summary "Plan presented"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-artifact.md](cli-artifact.md) | `artifact publish` |
| [cli-receipt.md](cli-receipt.md) | `receipt seal` |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-check.md](cli-check.md) | engine hooks: `on_seal` presentation checks |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 32 --to-seq 46

seq  at                        visit  node             type               detail
───  ────────────────────────  ─────  ───────────────  ─────────────────  ─────────────────────────────────────────────
 32  2026-09-24T14:18:21Z      v-003  shape.present    visit.admitted     source: v-002 / shape.examine-to-shape.present
 33  2026-09-24T14:18:21Z      v-003  shape.present    lifecycle.changed  admitted → examined → opened
 34  2026-09-24T14:25:00Z      v-003  shape.present    artifact.linked    presentation → run:artifacts/v-003/presentation.md
 35  2026-09-24T14:25:30Z      v-003  shape.present    receipt.linked     agent-receipt.schema.json
 36  2026-09-24T14:26:00Z      v-003  shape.present    lifecycle.changed  opened → closed → sealed
 37  2026-09-24T14:26:00Z      v-003  shape.present    visit.sealed       outcome: completed
 38  2026-09-24T14:26:00Z      v-003  shape.present    connection.taken   shape.present-to-shape.present.gate → shape.present.gate
 39  2026-09-24T14:26:00Z      v-004  shape.present.gate visit.admitted   source: v-003 / shape.present-to-shape.present.gate
```

**Route:** seal → `shape.present.gate`.

#### v-004 — `shape.present.gate`

User gate: options `refine` | `record`.

| Actor | Command |
|---|---|
| User | `foundry gate decide --decision record` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-gate.md](cli-gate.md) | `gate decide` |
| [cli-visit.md](cli-visit.md) | engine close/seal after gate resolution |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 39 --to-seq 50

seq  at                        visit  node               type               detail
───  ────────────────────────  ─────  ─────────────────  ─────────────────  ─────────────────────────────────────────────
 39  2026-09-24T14:26:00Z      v-004  shape.present.gate visit.admitted     source: v-003
 40  2026-09-24T14:26:00Z      v-004  shape.present.gate lifecycle.changed  admitted → examined → opened
 41  2026-09-24T14:26:01Z      v-004  shape.present.gate gate.presented     options: refine | record
 42  2026-09-24T14:27:10Z      v-004  shape.present.gate gate.resolved      decision: record
 43  2026-09-24T14:27:10Z      v-004  shape.present.gate lifecycle.changed  opened → closed → sealed
 44  2026-09-24T14:27:10Z      v-004  shape.present.gate visit.sealed       outcome: completed
 45  2026-09-24T14:27:10Z      v-004  shape.present.gate connection.taken   shape.present.gate-to-shape.record-record → shape.record
 46  2026-09-24T14:27:10Z      v-005  shape.record       visit.admitted     source: v-004
```

#### v-005 — `shape.record`

| Actor | Command |
|---|---|
| Steward | `foundry artifact publish plan --source run:artifacts/v-005/plan.md` |
| Steward | `foundry receipt seal --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json` |
| Steward | `foundry visit transition --summary "AC and plan recorded"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-artifact.md](cli-artifact.md) | `artifact publish` |
| [cli-receipt.md](cli-receipt.md) | `receipt seal` |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-check.md](cli-check.md) | engine hooks: `approved-ac-recorded`, `agent-receipt-sealed` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 46 --to-seq 60

seq  at                        visit  node         type               detail
───  ────────────────────────  ─────  ───────────  ─────────────────  ─────────────────────────────────────────────
 46  2026-09-24T14:27:10Z      v-005  shape.record visit.admitted     source: v-004
 47  2026-09-24T14:27:10Z      v-005  shape.record lifecycle.changed  admitted → examined → opened
 48  2026-09-24T14:35:00Z      v-005  shape.record artifact.linked    plan → run:artifacts/v-005/plan.md
 49  2026-09-24T14:35:30Z      v-005  shape.record receipt.linked     agent-receipt.schema.json
 50  2026-09-24T14:36:00Z      v-005  shape.record lifecycle.changed  opened → closed
 51  2026-09-24T14:36:01Z      v-005  shape.record check.recorded     on_seal: approved-ac-recorded → pass
 52  2026-09-24T14:36:01Z      v-005  shape.record policy.applied     approved-ac-recorded → continue
 53  2026-09-24T14:36:01Z      v-005  shape.record check.recorded     on_seal: agent-receipt-sealed → pass
 54  2026-09-24T14:36:01Z      v-005  shape.record policy.applied     agent-receipt-sealed → continue
 55  2026-09-24T14:36:01Z      v-005  shape.record lifecycle.changed  closed → sealed
 56  2026-09-24T14:36:01Z      v-005  shape.record visit.sealed       outcome: completed
 57  2026-09-24T14:36:01Z      v-005  shape.record connection.taken   → shape.record.gate
 58  2026-09-24T14:36:01Z      v-006  shape.record.gate visit.admitted source: v-005
```

#### v-006 — `shape.record.gate`

User confirms shared understanding before execute.

| Actor | Command |
|---|---|
| User | `foundry gate decide --decision record` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-gate.md](cli-gate.md) | `gate decide` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 58 --to-seq 68

seq  at                        visit  node              type               detail
───  ────────────────────────  ─────  ────────────────  ─────────────────  ─────────────────────────────────────────────
 58  2026-09-24T14:36:01Z      v-006  shape.record.gate visit.admitted     source: v-005
 59  2026-09-24T14:36:01Z      v-006  shape.record.gate gate.presented     options: (step gate)
 60  2026-09-24T14:37:00Z      v-006  shape.record.gate gate.resolved      decision: record
 61  2026-09-24T14:37:00Z      v-006  shape.record.gate visit.sealed       outcome: completed
 62  2026-09-24T14:37:00Z      v-006  shape.record.gate connection.taken   shape.record.gate-to-execute.start-record → execute.start
 63  2026-09-24T14:37:00Z      v-007  execute.start     visit.admitted     source: v-006
```

**Route:** `shape.record.gate-to-execute.start-record` → `execute.start`.

---

### Phase: execute

#### v-007 — `execute.start`

User gate; `/craft-execute` in product terms.

| Actor | Command |
|---|---|
| User | `foundry gate decide --decision start` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-gate.md](cli-gate.md) | `gate decide` |
| [cli-check.md](cli-check.md) | engine hook: `approved-ac-recorded` (on_examine) |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 63 --to-seq 74

seq  at                        visit  node          type               detail
───  ────────────────────────  ─────  ────────────  ─────────────────  ─────────────────────────────────────────────
 63  2026-09-24T14:37:00Z      v-007  execute.start visit.admitted     source: v-006
 64  2026-09-24T14:37:00Z      v-007  execute.start lifecycle.changed  admitted → examined
 65  2026-09-24T14:37:00Z      v-007  execute.start check.recorded     on_examine: approved-ac-recorded → pass
 66  2026-09-24T14:37:00Z      v-007  execute.start policy.applied     approved-ac-recorded → continue
 67  2026-09-24T14:37:00Z      v-007  execute.start gate.presented     options: start | …
 68  2026-09-24T14:38:00Z      v-007  execute.start gate.resolved      decision: start
 69  2026-09-24T14:38:00Z      v-007  execute.start visit.sealed       outcome: completed
 70  2026-09-24T14:38:00Z      v-007  execute.start connection.taken   → execute.intake
 71  2026-09-24T14:38:00Z      v-008  execute.intake visit.admitted    source: v-007
```

#### v-008 — `execute.intake`

| Actor | Command |
|---|---|
| Steward | `foundry app validate --workspace .` |
| Steward | `foundry check eval --check validate-git-clean-execute --workspace .` |
| Steward | `foundry receipt seal --schema registry:schemas/intake-receipt.schema.json --file run:receipts/intake.json` |
| Steward | `foundry visit transition --summary "Execute intake ready"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-app.md](cli-app.md) | `app validate` |
| [cli-check.md](cli-check.md) | `check eval`; engine hooks: `reexecute-within-limit`, `approved-ac-recorded`, `prior-shape-record-sealed`, `validate-manifest`, `validate-git-clean-execute`, `intake-receipt-sealed` |
| [cli-git.md](cli-git.md) | `git clean-check` (probe behind `validate-git-clean-execute`) |
| [cli-receipt.md](cli-receipt.md) | `receipt seal` |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 71 --to-seq 94

seq  at                        visit  node           type               detail
───  ────────────────────────  ─────  ─────────────  ─────────────────  ─────────────────────────────────────────────
 71  2026-09-24T14:38:00Z      v-008  execute.intake visit.admitted     source: v-007
 72  2026-09-24T14:38:00Z      v-008  execute.intake lifecycle.changed  admitted → examined
 73  2026-09-24T14:38:00Z      v-008  execute.intake check.recorded     on_examine: reexecute-within-limit → pass
 74  2026-09-24T14:38:00Z      v-008  execute.intake check.recorded     on_examine: approved-ac-recorded → pass
 75  2026-09-24T14:38:00Z      v-008  execute.intake check.recorded     on_examine: prior-shape-record-sealed → pass
 76  2026-09-24T14:38:01Z      v-008  execute.intake lifecycle.changed  examined → opened
 77  2026-09-24T14:38:01Z      v-008  execute.intake check.recorded     on_open: validate-manifest → pass
 78  2026-09-24T14:38:02Z      v-008  execute.intake check.recorded     on_open: validate-git-clean-execute → pass
 79  2026-09-24T14:40:00Z      v-008  execute.intake receipt.linked     intake-receipt.schema.json
 80  2026-09-24T14:40:30Z      v-008  execute.intake lifecycle.changed  opened → closed
 81  2026-09-24T14:40:31Z      v-008  execute.intake check.recorded     on_seal: intake-receipt-sealed → pass
 82  2026-09-24T14:40:31Z      v-008  execute.intake visit.sealed       outcome: completed
 83  2026-09-24T14:40:31Z      v-008  execute.intake connection.taken   → execute.intake.gate
 84  2026-09-24T14:40:31Z      v-009  execute.intake.gate visit.admitted source: v-008
```

#### v-009 — `execute.intake.gate`

Engine gate (`decider: engine`).

| Actor | Command |
|---|---|
| Engine | Records `gate.resolved` with `pass` (`decider: engine`; stewards do not call `gate decide`) |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-gate.md](cli-gate.md) | engine `gate.resolved` (no steward `gate decide`) |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 84 --to-seq 92

seq  at                        visit  node                type               detail
───  ────────────────────────  ─────  ──────────────────  ─────────────────  ─────────────────────────────────────────────
 84  2026-09-24T14:40:31Z      v-009  execute.intake.gate visit.admitted     source: v-008
 85  2026-09-24T14:40:31Z      v-009  execute.intake.gate gate.presented     (engine)
 86  2026-09-24T14:40:31Z      v-009  execute.intake.gate gate.resolved      decision: pass
 87  2026-09-24T14:40:31Z      v-009  execute.intake.gate visit.sealed       outcome: completed
 88  2026-09-24T14:40:31Z      v-009  execute.intake.gate connection.taken   execute.intake.gate-to-execute.branch-pass → execute.branch
 89  2026-09-24T14:40:31Z      v-010  execute.branch      visit.admitted     source: v-009
```

**Route:** `execute.intake.gate-to-execute.branch-pass` → `execute.branch`.

#### v-010 — `execute.branch`

| Actor | Command |
|---|---|
| Steward | `foundry branch create --run …` |
| Steward | `foundry visit transition --summary "Feature branch created"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-branch.md](cli-branch.md) | `branch create` |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-check.md](cli-check.md) | engine hook: `prior-execute-intake-sealed` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 89 --to-seq 102

seq  at                        visit  node           type               detail
───  ────────────────────────  ─────  ─────────────  ─────────────────  ─────────────────────────────────────────────
 89  2026-09-24T14:40:31Z      v-010  execute.branch visit.admitted     source: v-009
 90  2026-09-24T14:40:31Z      v-010  execute.branch check.recorded     on_examine: prior-execute-intake-sealed → pass
 91  2026-09-24T14:40:32Z      v-010  execute.branch lifecycle.changed  examined → opened
      (state updated: feature_branch, default_branch — not ledger events)
 92  2026-09-24T14:42:00Z      v-010  execute.branch lifecycle.changed  opened → closed → sealed
 93  2026-09-24T14:42:00Z      v-010  execute.branch visit.sealed       outcome: completed
 94  2026-09-24T14:42:00Z      v-010  execute.branch connection.taken   → execute.plan
 95  2026-09-24T14:42:00Z      v-011  execute.plan   visit.admitted     source: v-010
```

#### v-011 — `execute.plan`

| Actor | Command |
|---|---|
| Steward | `foundry graph validate --file run:artifacts/v-011/execution-graph.json` |
| Steward | `foundry artifact publish execution-graph --source run:artifacts/v-011/execution-graph.json` |
| Steward | `foundry artifact publish execute-brief --source run:artifacts/v-011/execute-brief.md` |
| Steward | `foundry receipt seal --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json` |
| Steward | `foundry visit transition --summary "Execution graph ready"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-graph.md](cli-graph.md) | `graph validate`, `graph ensure-reference` (on_open hook) |
| [cli-artifact.md](cli-artifact.md) | `artifact publish` |
| [cli-receipt.md](cli-receipt.md) | `receipt seal` |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-check.md](cli-check.md) | engine hooks: `ensure-execution-graph-reference`, `execution-graph-set`, `agent-receipt-sealed` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 95 --to-seq 114

seq  at                        visit  node         type               detail
───  ────────────────────────  ─────  ───────────  ─────────────────  ─────────────────────────────────────────────
 95  2026-09-24T14:42:00Z      v-011  execute.plan visit.admitted     source: v-010
 96  2026-09-24T14:42:01Z      v-011  execute.plan lifecycle.changed  examined → opened
 97  2026-09-24T14:42:01Z      v-011  execute.plan check.recorded     on_open: ensure-execution-graph-reference → pass
 98  2026-09-24T14:50:00Z      v-011  execute.plan artifact.linked    execution-graph
 99  2026-09-24T14:50:01Z      v-011  execute.plan artifact.linked    execute-brief
100  2026-09-24T14:50:30Z      v-011  execute.plan receipt.linked     agent-receipt.schema.json
101  2026-09-24T14:51:00Z      v-011  execute.plan check.recorded     on_seal: execution-graph-set → pass
102  2026-09-24T14:51:00Z      v-011  execute.plan check.recorded     on_seal: agent-receipt-sealed → pass
103  2026-09-24T14:51:00Z      v-011  execute.plan visit.sealed       outcome: completed
104  2026-09-24T14:51:00Z      v-011  execute.plan connection.taken   → execute.build
105  2026-09-24T14:51:00Z      v-012  execute.build visit.admitted    source: v-011
```

#### v-012 — `execute.build`

Builders commit via transition (see [cli-visit.md](cli-visit.md) / [cli-git.md](cli-git.md)).

| Actor | Command |
|---|---|
| Steward | `foundry build build` (next ready work item, as configured) |
| Steward | `foundry visit transition --summary "Build graph complete"` (may include per-item commits) |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-build.md](cli-build.md) | `build build` |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-git.md](cli-git.md) | commit semantics (see [gaps.md](gaps.md)) |
| [cli-check.md](cli-check.md) | engine hooks: `validate_build_exit`, `agent-receipt-sealed` |
| [cli-ledger.md](cli-ledger.md) | `ledger show`, `ledger tail` (long-running) |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 105 --to-seq 168

seq  at                        visit  node          type               detail
───  ────────────────────────  ─────  ────────────  ─────────────────  ─────────────────────────────────────────────
105  2026-09-24T14:51:00Z      v-012  execute.build visit.admitted     source: v-011
106  2026-09-24T14:51:01Z      v-012  execute.build lifecycle.changed  examined → opened
      … (build work items; artifact.linked per graph node as configured) …
160  2026-09-24T16:10:00Z      v-012  execute.build lifecycle.changed  opened → closed
161  2026-09-24T16:10:01Z      v-012  execute.build check.recorded     on_seal: validate_build_exit → pass
162  2026-09-24T16:10:01Z      v-012  execute.build check.recorded     on_seal: agent-receipt-sealed → pass
163  2026-09-24T16:10:01Z      v-012  execute.build visit.sealed       outcome: completed
164  2026-09-24T16:10:01Z      v-012  execute.build connection.taken   → execute.test
165  2026-09-24T16:10:01Z      v-013  execute.test  visit.admitted     source: v-012

$ foundry ledger tail --run porcelain-0007 --limit 3

seq  at                        visit  node          type               detail
───  ────────────────────────  ─────  ────────────  ─────────────────  ─────────────────────────────────────────────
163  2026-09-24T16:10:01Z      v-012  execute.build visit.sealed       outcome: completed
164  2026-09-24T16:10:01Z      v-012  execute.build connection.taken   → execute.test
165  2026-09-24T16:10:01Z      v-013  execute.test  visit.admitted     source: v-012
```

#### v-013 — `execute.test`

| Actor | Command |
|---|---|
| Steward | `foundry build test` |
| Steward | `foundry receipt seal --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json` |
| Steward | `foundry visit transition --summary "Tests passed"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-build.md](cli-build.md) | `build test` |
| [cli-receipt.md](cli-receipt.md) | `receipt seal` |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-check.md](cli-check.md) | engine hooks: `agent-receipt-sealed` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 165 --to-seq 180

seq  at                        visit  node         type               detail
───  ────────────────────────  ─────  ───────────  ─────────────────  ─────────────────────────────────────────────
165  2026-09-24T16:10:01Z      v-013  execute.test visit.admitted     source: v-012
166  2026-09-24T16:10:02Z      v-013  execute.test lifecycle.changed  examined → opened
167  2026-09-24T16:25:00Z      v-013  execute.test receipt.linked     agent-receipt.schema.json
168  2026-09-24T16:25:30Z      v-013  execute.test check.recorded     on_seal: agent-receipt-sealed → pass
169  2026-09-24T16:25:30Z      v-013  execute.test visit.sealed       outcome: completed
170  2026-09-24T16:25:30Z      v-013  execute.test connection.taken   → execute.test.gate
171  2026-09-24T16:25:30Z      v-014  execute.test.gate visit.admitted source: v-013
```

#### v-014 — `execute.test.gate`

Engine gate: `pass` | `repair`.

| Actor | Command |
|---|---|
| Engine | Records `gate.resolved` (`decider: engine`) |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-gate.md](cli-gate.md) | engine `gate.resolved` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 171 --to-seq 178

seq  at                        visit  node              type               detail
───  ────────────────────────  ─────  ─────────────────  ─────────────────  ─────────────────────────────────────────────
171  2026-09-24T16:25:30Z      v-014  execute.test.gate visit.admitted     source: v-013
172  2026-09-24T16:25:30Z      v-014  execute.test.gate gate.resolved      decision: pass
173  2026-09-24T16:25:30Z      v-014  execute.test.gate visit.sealed       outcome: completed
174  2026-09-24T16:25:30Z      v-014  execute.test.gate connection.taken   execute.test.gate-to-execute.commit-pass → execute.commit
175  2026-09-24T16:25:30Z      v-015  execute.commit    visit.admitted     source: v-014
```

**Route (happy):** `execute.test.gate-to-execute.commit-pass` → `execute.commit`.

#### v-015 — `execute.commit`

| Actor | Command |
|---|---|
| Steward | `foundry artifact publish final-commit --ref git:commit/abc1234` |
| Steward | `foundry receipt seal --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json` |
| Steward | `foundry visit transition --summary "Final execute commit recorded"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-artifact.md](cli-artifact.md) | `artifact publish` (git reference) |
| [cli-receipt.md](cli-receipt.md) | `receipt seal` |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-check.md](cli-check.md) | engine hooks: `final-commit-recorded`, `agent-receipt-sealed` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 175 --to-seq 190

seq  at                        visit  node           type               detail
───  ────────────────────────  ─────  ─────────────  ─────────────────  ─────────────────────────────────────────────
175  2026-09-24T16:25:30Z      v-015  execute.commit visit.admitted     source: v-014
176  2026-09-24T16:26:00Z      v-015  execute.commit artifact.linked    final-commit → git:commit/abc1234
177  2026-09-24T16:26:30Z      v-015  execute.commit receipt.linked     agent-receipt.schema.json
178  2026-09-24T16:27:00Z      v-015  execute.commit check.recorded     on_seal: final-commit-recorded → pass
179  2026-09-24T16:27:00Z      v-015  execute.commit check.recorded     on_seal: agent-receipt-sealed → pass
180  2026-09-24T16:27:00Z      v-015  execute.commit visit.sealed       outcome: completed
181  2026-09-24T16:27:00Z      v-015  execute.commit connection.taken   → execute.commit.gate
182  2026-09-24T16:27:00Z      v-016  execute.commit.gate visit.admitted source: v-015
```

#### v-016 — `execute.commit.gate`

Engine gate; also enforces re-verify limit before verify entry.

| Actor | Command |
|---|---|
| Engine | Records `gate.resolved` (`decider: engine`) |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-gate.md](cli-gate.md) | engine `gate.resolved` |
| [cli-check.md](cli-check.md) | engine hooks: `reverify-within-limit`, `prior-execute-commit-sealed`, `final-commit-recorded` |
| [cli-ledger.md](cli-ledger.md) | `ledger show`, `ledger query` (`reverify-within-limit`) |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 182 --to-seq 196

seq  at                        visit  node                type               detail
───  ────────────────────────  ─────  ──────────────────  ─────────────────  ─────────────────────────────────────────────
182  2026-09-24T16:27:00Z      v-016  execute.commit.gate visit.admitted     source: v-015
183  2026-09-24T16:27:00Z      v-016  execute.commit.gate lifecycle.changed  admitted → examined
184  2026-09-24T16:27:00Z      v-016  execute.commit.gate check.recorded     on_examine: reverify-within-limit → pass
185  2026-09-24T16:27:00Z      v-016  execute.commit.gate check.recorded     on_examine: prior-execute-commit-sealed → pass
186  2026-09-24T16:27:00Z      v-016  execute.commit.gate check.recorded     on_examine: final-commit-recorded → pass
187  2026-09-24T16:27:00Z      v-016  execute.commit.gate gate.resolved      decision: pass
188  2026-09-24T16:27:00Z      v-016  execute.commit.gate visit.sealed       outcome: completed
189  2026-09-24T16:27:00Z      v-016  execute.commit.gate connection.taken   execute.commit.gate-to-verify.intake-pass → verify.intake
190  2026-09-24T16:27:00Z      v-017  verify.intake       visit.admitted     source: v-016
```

**Route:** `execute.commit.gate-to-verify.intake-pass` → `verify.intake`.

---

### Phase: verify

#### v-017 — `verify.intake`

| Actor | Command |
|---|---|
| Steward | `foundry app validate --workspace .` |
| Steward | `foundry check eval --check validate-verify-context` |
| Steward | `foundry artifact publish branch-diff --source run:artifacts/v-017/branch.diff` |
| Steward | `foundry receipt seal --schema registry:schemas/intake-receipt.schema.json --file run:receipts/intake.json` |
| Steward | `foundry visit transition --summary "Verify intake ready"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-app.md](cli-app.md) | `app validate` |
| [cli-check.md](cli-check.md) | `check eval`; engine hooks: `validate-verify-context`, `intake-receipt-sealed` |
| [cli-artifact.md](cli-artifact.md) | `artifact publish` |
| [cli-receipt.md](cli-receipt.md) | `receipt seal` |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 190 --to-seq 208

seq  at                        visit  node          type               detail
───  ────────────────────────  ─────  ────────────  ─────────────────  ─────────────────────────────────────────────
190  2026-09-24T16:27:00Z      v-017  verify.intake visit.admitted     source: v-016
191  2026-09-24T16:27:01Z      v-017  verify.intake lifecycle.changed  examined → opened
192  2026-09-24T16:30:00Z      v-017  verify.intake artifact.linked    branch-diff
193  2026-09-24T16:30:30Z      v-017  verify.intake receipt.linked     intake-receipt.schema.json
194  2026-09-24T16:31:00Z      v-017  verify.intake visit.sealed       outcome: completed
195  2026-09-24T16:31:00Z      v-017  verify.intake connection.taken   → verify.intake.gate
196  2026-09-24T16:31:00Z      v-018  verify.intake.gate visit.admitted source: v-017
```

#### v-018 — `verify.intake.gate`

| Actor | Command |
|---|---|
| Engine | Records `gate.resolved` (`decider: engine`) |

Failure policy: `halt` (verify blocked entirely).

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-gate.md](cli-gate.md) | engine `gate.resolved` |
| [cli-run.md](cli-run.md) | `run show` (halted status on fail) |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger (happy — pass)**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 196 --to-seq 204

seq  at                        visit  node               type               detail
───  ────────────────────────  ─────  ─────────────────  ─────────────────  ─────────────────────────────────────────────
196  2026-09-24T16:31:00Z      v-018  verify.intake.gate visit.admitted     source: v-017
197  2026-09-24T16:31:00Z      v-018  verify.intake.gate gate.resolved      decision: pass
198  2026-09-24T16:31:00Z      v-018  verify.intake.gate visit.sealed       outcome: completed
199  2026-09-24T16:31:00Z      v-018  verify.intake.gate connection.taken   → verify.acceptance
200  2026-09-24T16:31:00Z      v-019  verify.acceptance  visit.admitted     source: v-018
```

#### v-019 — `verify.acceptance`

| Actor | Command |
|---|---|
| Steward | `foundry artifact publish verify-findings --source run:artifacts/v-019/verify-findings.json` |
| Steward | `foundry visit transition --summary "Acceptance validation complete"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-artifact.md](cli-artifact.md) | `artifact publish` |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 200 --to-seq 212

seq  at                        visit  node              type               detail
───  ────────────────────────  ─────  ────────────────  ─────────────────  ─────────────────────────────────────────────
200  2026-09-24T16:31:00Z      v-019  verify.acceptance visit.admitted     source: v-018
201  2026-09-24T16:31:01Z      v-019  verify.acceptance lifecycle.changed  examined → opened
202  2026-09-24T16:45:00Z      v-019  verify.acceptance artifact.linked    verify-findings
203  2026-09-24T16:45:30Z      v-019  verify.acceptance visit.sealed       outcome: completed
204  2026-09-24T16:45:30Z      v-019  verify.acceptance connection.taken   → verify.acceptance.gate
205  2026-09-24T16:45:30Z      v-020  verify.acceptance.gate visit.admitted source: v-019
```

#### v-020 — `verify.acceptance.gate`

Engine routes: `pass` | `replan` | `reshape` | `rework_execute`.

| Actor | Command |
|---|---|
| Engine | Records `gate.resolved` (`decider: engine`) |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-gate.md](cli-gate.md) | engine `gate.resolved` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger (happy — pass)**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 205 --to-seq 214

seq  at                        visit  node                   type               detail
───  ────────────────────────  ─────  ─────────────────────  ─────────────────  ─────────────────────────────────────────────
205  2026-09-24T16:45:30Z      v-020  verify.acceptance.gate visit.admitted     source: v-019
206  2026-09-24T16:45:30Z      v-020  verify.acceptance.gate gate.resolved      decision: pass
207  2026-09-24T16:45:30Z      v-020  verify.acceptance.gate visit.sealed       outcome: completed
208  2026-09-24T16:45:30Z      v-020  verify.acceptance.gate connection.taken   verify.acceptance.gate-to-verify.code_quality-pass
209  2026-09-24T16:45:30Z      v-021  verify.code_quality    visit.admitted     source: v-020
```

**Route (happy):** `verify.acceptance.gate-to-verify.code_quality-pass`.

#### v-021 — `verify.code_quality`

Skipped entirely when `config.review.enabled` is false (`on_examine` policy `skip` → seal `not_applicable`). Happy path assumes review enabled.

| Actor | Command |
|---|---|
| Steward | `foundry artifact publish code-quality-report --source run:artifacts/v-021/code-quality-report.md` |
| Steward | `foundry visit transition --summary "Code quality review complete"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-artifact.md](cli-artifact.md) | `artifact publish` |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-check.md](cli-check.md) | engine hook: `review-enabled` (on_examine) |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 209 --to-seq 222

seq  at                        visit  node                type               detail
───  ────────────────────────  ─────  ──────────────────  ─────────────────  ─────────────────────────────────────────────
209  2026-09-24T16:45:30Z      v-021  verify.code_quality visit.admitted     source: v-020
210  2026-09-24T16:45:31Z      v-021  verify.code_quality check.recorded     on_examine: review-enabled → pass
211  2026-09-24T16:45:31Z      v-021  verify.code_quality lifecycle.changed  examined → opened
212  2026-09-24T17:00:00Z      v-021  verify.code_quality artifact.linked    code-quality-report
213  2026-09-24T17:00:30Z      v-021  verify.code_quality visit.sealed       outcome: completed
214  2026-09-24T17:00:30Z      v-021  verify.code_quality connection.taken   → verify.code_quality.gate
215  2026-09-24T17:00:30Z      v-022  verify.code_quality.gate visit.admitted source: v-021
```

#### v-022 — `verify.code_quality.gate`

| Actor | Command |
|---|---|
| Engine | Records `gate.resolved` (`decider: engine`) |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-gate.md](cli-gate.md) | engine `gate.resolved` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 215 --to-seq 224

seq  at                        visit  node                   type               detail
───  ────────────────────────  ─────  ─────────────────────  ─────────────────  ─────────────────────────────────────────────
215  2026-09-24T17:00:30Z      v-022  verify.code_quality.gate visit.admitted     source: v-021
216  2026-09-24T17:00:30Z      v-022  verify.code_quality.gate gate.resolved      decision: pass
217  2026-09-24T17:00:30Z      v-022  verify.code_quality.gate visit.sealed       outcome: completed
218  2026-09-24T17:00:30Z      v-022  verify.code_quality.gate connection.taken   → verify.code_review
219  2026-09-24T17:00:30Z      v-023  verify.code_review       visit.admitted     source: v-022
```

#### v-023 — `verify.code_review`

Human single-turn review.

| Actor | Command |
|---|---|
| Steward | `foundry artifact publish verify-notes --source run:artifacts/v-023/verify-notes.md` |
| Steward | `foundry visit transition --summary "Human review complete"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-artifact.md](cli-artifact.md) | `artifact publish` |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 219 --to-seq 232

seq  at                        visit  node               type               detail
───  ────────────────────────  ─────  ─────────────────  ─────────────────  ─────────────────────────────────────────────
219  2026-09-24T17:00:30Z      v-023  verify.code_review visit.admitted     source: v-022
220  2026-09-24T17:00:31Z      v-023  verify.code_review lifecycle.changed  examined → opened
221  2026-09-24T17:15:00Z      v-023  verify.code_review artifact.linked    verify-notes
222  2026-09-24T17:15:30Z      v-023  verify.code_review visit.sealed       outcome: completed
223  2026-09-24T17:15:30Z      v-023  verify.code_review connection.taken   → verify.code_review.gate
224  2026-09-24T17:15:30Z      v-024  verify.code_review.gate visit.admitted source: v-023
```

#### v-024 — `verify.code_review.gate`

| Actor | Command |
|---|---|
| User | `foundry gate decide --decision approve` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-gate.md](cli-gate.md) | `gate decide` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 224 --to-seq 234

seq  at                        visit  node                   type               detail
───  ────────────────────────  ─────  ─────────────────────  ─────────────────  ─────────────────────────────────────────────
224  2026-09-24T17:15:30Z      v-024  verify.code_review.gate visit.admitted     source: v-023
225  2026-09-24T17:15:30Z      v-024  verify.code_review.gate gate.presented     options: approve | reshape | repair
226  2026-09-24T17:20:00Z      v-024  verify.code_review.gate gate.resolved      decision: approve
227  2026-09-24T17:20:00Z      v-024  verify.code_review.gate visit.sealed       outcome: completed
228  2026-09-24T17:20:00Z      v-024  verify.code_review.gate connection.taken   verify.code_review.gate-to-verify.complete-approve
229  2026-09-24T17:20:00Z      v-025  verify.complete         visit.admitted     source: v-024
```

#### v-025 — `verify.complete`

| Actor | Command |
|---|---|
| Steward | `foundry visit transition --summary "Verify phase ready to complete"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-check.md](cli-check.md) | engine hook: `code-review-approved` (on_examine) |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 229 --to-seq 240

seq  at                        visit  node            type               detail
───  ────────────────────────  ─────  ──────────────  ─────────────────  ─────────────────────────────────────────────
229  2026-09-24T17:20:00Z      v-025  verify.complete visit.admitted     source: v-024
230  2026-09-24T17:20:00Z      v-025  verify.complete check.recorded     on_examine: code-review-approved → pass
231  2026-09-24T17:20:01Z      v-025  verify.complete lifecycle.changed  examined → opened
232  2026-09-24T17:20:30Z      v-025  verify.complete visit.sealed       outcome: completed
233  2026-09-24T17:20:30Z      v-025  verify.complete connection.taken   → verify.complete.gate
234  2026-09-24T17:20:30Z      v-026  verify.complete.gate visit.admitted source: v-025
```

#### v-026 — `verify.complete.gate`

| Actor | Command |
|---|---|
| User | `foundry gate decide --decision complete` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-gate.md](cli-gate.md) | `gate decide` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 234 --to-seq 244

seq  at                        visit  node                type               detail
───  ────────────────────────  ─────  ──────────────────  ─────────────────  ─────────────────────────────────────────────
234  2026-09-24T17:20:30Z      v-026  verify.complete.gate visit.admitted     source: v-025
235  2026-09-24T17:20:30Z      v-026  verify.complete.gate gate.presented     options: complete | …
236  2026-09-24T17:21:00Z      v-026  verify.complete.gate gate.resolved      decision: complete
237  2026-09-24T17:21:00Z      v-026  verify.complete.gate visit.sealed       outcome: completed
238  2026-09-24T17:21:00Z      v-026  verify.complete.gate connection.taken   verify.complete.gate-to-deliver.stub-complete
239  2026-09-24T17:21:00Z      v-027  deliver.stub         visit.admitted     source: v-026
```

**Route:** `verify.complete.gate-to-deliver.stub-complete`.

---

### Phase: deliver (stub)

#### v-027 — `deliver.stub` (terminal)

| Actor | Command |
|---|---|
| Steward | `foundry visit transition --summary "Deliver stub complete"` |

**CLI specs**

| Document | Commands in this visit |
|---|---|
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-run.md](cli-run.md) | `run show` (terminal `completed` status) |
| [cli-ledger.md](cli-ledger.md) | `ledger show`, `ledger tail` |

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 239 --to-seq 244

seq  at                        visit  node         type               detail
───  ────────────────────────  ─────  ───────────  ─────────────────  ─────────────────────────────────────────────
239  2026-09-24T17:21:00Z      v-027  deliver.stub visit.admitted     source: v-026
240  2026-09-24T17:21:01Z      v-027  deliver.stub lifecycle.changed  examined → opened
241  2026-09-24T17:21:30Z      v-027  deliver.stub lifecycle.changed  opened → closed
242  2026-09-24T17:21:30Z      v-027  deliver.stub lifecycle.changed  closed → sealed
243  2026-09-24T17:21:30Z      v-027  deliver.stub visit.sealed       outcome: completed
244  2026-09-24T17:21:30Z      —      —            run.status_changed running → completed
245  2026-09-24T17:21:30Z      —      —            run.completed      terminal: v-027 / deliver.stub
```

**Run status:** `completed`. No further visits.

```text
$ foundry run show --run porcelain-0007

run_id:      porcelain-0007
status:      completed
visit_id:    v-027
node_id:     deliver.stub
lifecycle:   sealed
outcome:     completed
ledger_seq:  245
```

Example final JSON response from the closing transition:

```json
{
  "ok": true,
  "run_id": "porcelain-0007",
  "status": "completed",
  "visit": {
    "id": "v-027",
    "node_id": "deliver.stub",
    "lifecycle": "sealed",
    "outcome": "completed"
  },
  "ledger_seq": 245,
  "events_appended": ["lifecycle.changed", "visit.sealed", "run.status_changed", "run.completed"]
}
```

---

## Rework and failure paths

Each subsection: **trigger**, **CLI surface**, **ledger**, **next position**.

### Policy `reopen` (on_seal fail → same visit reopened)

**Trigger:** `on_seal` check fails with policy action `reopen` (for example `intake-receipt-sealed` on `shape.intake`, `validate_build_exit` on `execute.build`, `final-commit-recorded` on `execute.commit`).

**CLI specs**

| Document | Commands in this path |
|---|---|
| [cli-visit.md](cli-visit.md) | `visit transition` (retry on same visit) |
| [cli-receipt.md](cli-receipt.md) | `receipt seal` (fix evidence) |
| [cli-artifact.md](cli-artifact.md) | `artifact publish` (fix artifacts) |
| [cli-build.md](cli-build.md) | `build build` (fix build on `execute.build`) |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**CLI surface:** Steward fixes evidence or artifacts, then calls `foundry visit transition` again on the **same** `visit_id`. No new visit is created.

**Ledger**

```text
$ foundry visit transition --run porcelain-0007 --summary "Fixed intake receipt"

$ foundry ledger tail --run porcelain-0007 --limit 4

seq  at                        visit  node          type               detail
───  ────────────────────────  ─────  ────────────  ─────────────────  ─────────────────────────────────────────────
 18  2026-09-24T14:05:00Z      v-001  shape.intake  check.recorded     on_seal: intake-receipt-sealed → fail
 19  2026-09-24T14:05:00Z      v-001  shape.intake  policy.applied     intake-receipt-sealed → reopen
 20  2026-09-24T14:05:00Z      v-001  shape.intake  lifecycle.changed  closed → opened
      (no visit.sealed; no connection.taken)
```

**Next:** Visit stays on the same node in `opened`. Run status remains `running`.

### `execute.test.gate` repair → `execute.build` (`loop=reexecute`)

**Trigger:** Verification fails; engine resolves gate with `repair`.

**CLI specs**

| Document | Commands in this path |
|---|---|
| [cli-gate.md](cli-gate.md) | engine `gate.resolved` (`decider: engine`) |
| [cli-build.md](cli-build.md) | `build build` (repairer on re-admitted `execute.build`) |
| [cli-visit.md](cli-visit.md) | `visit transition` |
| [cli-check.md](cli-check.md) | `reexecute-within-limit` on re-entry |
| [cli-ledger.md](cli-ledger.md) | `ledger show`, `ledger query` |

**CLI surface:** Engine records `gate.resolved` with `repair`. Repairer steward re-enters `execute.build` after routing.

**Ledger**

```text
$ foundry ledger show --run porcelain-0007 --from-seq 171 --to-seq 178

seq  at                        visit  node              type               detail
───  ────────────────────────  ─────  ─────────────────  ─────────────────  ─────────────────────────────────────────────
172  2026-09-24T16:25:30Z      v-014  execute.test.gate gate.resolved      decision: repair
173  2026-09-24T16:25:30Z      v-014  execute.test.gate visit.sealed       outcome: completed
174  2026-09-24T16:25:30Z      v-014  execute.test.gate connection.taken   loop: reexecute → execute.build
175  2026-09-24T16:25:31Z      v-012b execute.build    visit.admitted     source: v-014 / repair loop
```

**Next:** New visit on `execute.build`; then `execute.test` → gate again. Limited by check `reexecute-within-limit` on `execute.build` / `execute.plan` / `execute.intake` on_examine.

### `verify.acceptance.gate` — replan, reshape, rework_execute

**Trigger:** Acceptance validation fails; engine gate selects non-`pass` decision.

| Decision | Connection | CLI / steward | Next node |
|---|---|---|---|
| `replan` | `verify.acceptance.gate-to-execute.plan-replan` | Engine resolves gate; planner steward | `execute.plan` (new visit) |
| `reshape` | `verify.acceptance.gate-to-shape.intake-reshape` | Engine resolves gate; shape steward | `shape.intake` (new visit, `loop: reshape`) |
| `rework_execute` | `verify.acceptance.gate-to-execute.intake-rework_execute` | Engine resolves gate | `execute.intake` (new visit) |

**CLI specs**

| Document | Commands in this path |
|---|---|
| [cli-gate.md](cli-gate.md) | engine `gate.resolved` |
| [cli-visit.md](cli-visit.md) | steward work on target node |
| [cli-check.md](cli-check.md) | `reshape-within-limit`, acceptance checks |
| [cli-ledger.md](cli-ledger.md) | `ledger show`, `ledger query` (`history.count(..., loop='reshape')`) |

**Ledger (example — reshape)**

```text
$ foundry ledger tail --run porcelain-0007 --limit 5

seq  at                        visit  node                   type               detail
───  ────────────────────────  ─────  ─────────────────────  ─────────────────  ─────────────────────────────────────────────
206  2026-09-24T16:45:30Z      v-020  verify.acceptance.gate gate.resolved      decision: reshape
207  2026-09-24T16:45:30Z      v-020  verify.acceptance.gate visit.sealed       outcome: completed
208  2026-09-24T16:45:30Z      v-020  verify.acceptance.gate connection.taken   loop: reshape → shape.intake
209  2026-09-24T16:45:31Z      v-001b shape.intake           visit.admitted     source: reshape loop
210  2026-09-24T16:45:31Z      v-001b shape.intake           check.recorded     on_examine: reshape-within-limit → pass
```

**Limits:** `reshape-within-limit` on `shape.intake` on_examine; failure → `escalate`.

### `verify.code_quality.gate` repair; skip when review disabled

**Skip path (review disabled)**

**Trigger:** `verify.code_quality` on_examine check `review-enabled` fails → policy `skip` → seal `not_applicable`.

**CLI specs**

| Document | Commands in this path |
|---|---|
| [cli-check.md](cli-check.md) | engine hook: `review-enabled` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**CLI surface:** No steward artifact commands required. Engine seals without opening.

**Ledger**

```text
$ foundry ledger tail --run porcelain-0007 --limit 5

seq  at                        visit  node                type               detail
───  ────────────────────────  ─────  ──────────────────  ─────────────────  ─────────────────────────────────────────────
209  2026-09-24T16:45:30Z      v-021  verify.code_quality visit.admitted     source: v-020
210  2026-09-24T16:45:31Z      v-021  verify.code_quality check.recorded     on_examine: review-enabled → fail
211  2026-09-24T16:45:31Z      v-021  verify.code_quality policy.applied     review-enabled → skip
212  2026-09-24T16:45:31Z      v-021  verify.code_quality visit.sealed       outcome: not_applicable
213  2026-09-24T16:45:31Z      v-021  verify.code_quality connection.taken   verify.code_quality-to-verify.code_review-skipped
```

**Next:** `verify.code_review` (human review still runs when acceptance passed).

**Repair path (review enabled, quality fails)**

**Trigger:** Engine resolves `verify.code_quality.gate` with `repair`.

**CLI specs**

| Document | Commands in this path |
|---|---|
| [cli-gate.md](cli-gate.md) | engine `gate.resolved` (`repair`) |
| [cli-build.md](cli-build.md) | repairer on `execute.build` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger tail --run porcelain-0007 --limit 3

seq  at                        visit  node                   type               detail
───  ────────────────────────  ─────  ─────────────────────  ─────────────────  ─────────────────────────────────────────────
216  2026-09-24T17:00:30Z      v-022  verify.code_quality.gate gate.resolved      decision: repair
217  2026-09-24T17:00:30Z      v-022  verify.code_quality.gate connection.taken   loop: reexecute → execute.build
218  2026-09-24T17:00:31Z      v-012c execute.build            visit.admitted     repair loop
```

### `verify.code_review.gate` — approve, reshape, repair

| Decision | Route | Meaning |
|---|---|---|
| `approve` | `verify.code_review.gate-to-verify.complete-approve` | Continue to `verify.complete` |
| `reshape` | `verify.code_review.gate-to-shape.intake-reshape` | AC wrong; reshape (`loop: reshape`) |
| `repair` | `verify.code_review.gate-to-execute.build-repair` | Standards fix; `loop: reexecute` |

**CLI specs**

| Document | Commands in this path |
|---|---|
| [cli-gate.md](cli-gate.md) | `gate decide` (user decider) |
| [cli-visit.md](cli-visit.md) | steward work on routed node |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**CLI surface:** `foundry gate decide`.

**Ledger (reshape example)**

```text
$ foundry ledger tail --run porcelain-0007 --limit 4

seq  at                        visit  node                   type               detail
───  ────────────────────────  ─────  ─────────────────────  ─────────────────  ─────────────────────────────────────────────
226  2026-09-24T17:20:00Z      v-024  verify.code_review.gate gate.resolved      decision: reshape
227  2026-09-24T17:20:00Z      v-024  verify.code_review.gate visit.sealed       outcome: completed
228  2026-09-24T17:20:00Z      v-024  verify.code_review.gate connection.taken   loop: reshape → shape.intake
229  2026-09-24T17:20:01Z      v-001c shape.intake           visit.admitted     reshape loop
```

### `shape.examine.gate` when open questions ≠ 0

**Trigger:** `state.open_clarifying_questions_count != 0` after `shape.examine` seal; fast lane ineligible.

**CLI specs**

| Document | Commands in this path |
|---|---|
| [cli-gate.md](cli-gate.md) | `gate decide` (user gate on `shape.examine.gate`) |
| [cli-visit.md](cli-visit.md) | `visit transition` on `shape.examine` |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Ledger**

```text
$ foundry ledger tail --run porcelain-0007 --limit 3

seq  at                        visit  node               type               detail
───  ────────────────────────  ─────  ─────────────────  ─────────────────  ─────────────────────────────────────────────
 30  2026-09-24T14:18:21Z      v-002  shape.examine      connection.taken   shape.examine-to-shape.examine.gate (not fast lane)
 31  2026-09-24T14:18:21Z      v-002a shape.examine.gate visit.admitted     gate before shape.present
```

### Escalation when loop limits exceeded

**Trigger:** History check fails on_examine — `reshape-within-limit`, `reexecute-within-limit`, or `reverify-within-limit` — with policy `escalate`.

| Check | Node(s) | Default limit |
|---|---|---|
| `reshape-within-limit` | `shape.intake` | `config.limits.reshape` (2) |
| `reexecute-within-limit` | `execute.intake`, `execute.plan`, `execute.build` | `config.limits.reexecute` (2) |
| `reverify-within-limit` | `execute.commit.gate` on_examine | `config.limits.reverify` (2) |

**CLI specs**

| Document | Commands in this path |
|---|---|
| [cli-escalation.md](cli-escalation.md) | `escalation show`, `escalation resolve` |
| [cli-run.md](cli-run.md) | `run show`, `run recover` |
| [cli-ledger.md](cli-ledger.md) | `ledger show`, `ledger query` |
| [cli-check.md](cli-check.md) | limit checks |

**CLI surface:** Run pauses. Operator uses escalation resolve:

```bash
foundry escalation resolve --resolution accept --operator lynn --reason "Proceed despite limit"
# or: retry | halt
```

**Ledger**

```text
$ foundry ledger tail --run porcelain-0007 --limit 6

seq  at                        visit  node          type               detail
───  ────────────────────────  ─────  ────────────  ─────────────────  ─────────────────────────────────────────────
  4  2026-09-24T14:45:31Z      v-001d shape.intake  check.recorded     on_examine: reshape-within-limit → fail
  5  2026-09-24T14:45:31Z      v-001d shape.intake  policy.applied     reshape-within-limit → escalate
  6  2026-09-24T14:45:31Z      —      —             run.status_changed running → paused
  7  2026-09-24T14:45:31Z      —      —             escalation.raised    check: reshape-within-limit

$ foundry escalation resolve --resolution accept --operator lynn --reason "Proceed despite limit"

$ foundry ledger tail --run porcelain-0007 --limit 2

seq  at                        visit  node  type               detail
───  ────────────────────────  ─────  ────  ─────────────────  ─────────────────────────────────────────────
  8  2026-09-24T14:50:00Z      —      —     escalation.resolved resolution: accept; operator: lynn
  9  2026-09-24T14:50:00Z      —      —     run.status_changed paused → running
```

**Next:**

| Resolution | Effect |
|---|---|
| `accept` | Treat as `continue`; admit or proceed past limiting check |
| `retry` | Re-evaluate same check |
| `halt` | Run → `halted`; explicit `foundry run recover` required |

### Run statuses

| Status | Typical CLI trigger | Resume |
|---|---|---|
| `running` | Normal operation | n/a |
| `paused` | Policy `escalate` | [foundry escalation resolve](cli-escalation.md) |
| `halted` | Policy `halt` (for example intake gate fail) | [foundry run recover](cli-run.md) with operator reason |
| `execution_error` | `check.errored` | [foundry run recover](cli-run.md) after the environment is fixed |
| `definition_error` | Invalid registry or zero eligible connections | Fix flow; no resume |
| `completed` | Terminal `deliver.stub` sealed | none |

**CLI specs**

| Document | Commands in this path |
|---|---|
| [cli-run.md](cli-run.md) | `run show`, `run recover` |
| [cli-escalation.md](cli-escalation.md) | `escalation resolve` |
| [cli-check.md](cli-check.md) | `check eval` (execution errors) |
| [cli-ledger.md](cli-ledger.md) | `ledger show` |

**Halt example (`verify.intake.gate`)**

```text
$ foundry ledger tail --run porcelain-0007 --limit 4

seq  at                        visit  node               type               detail
───  ────────────────────────  ─────  ─────────────────  ─────────────────  ─────────────────────────────────────────────
197  2026-09-24T16:31:00Z      v-018  verify.intake.gate gate.resolved      decision: fail
198  2026-09-24T16:31:00Z      v-018  verify.intake.gate policy.applied     → halt
199  2026-09-24T16:31:00Z      —      —                  run.status_changed running → halted

$ foundry run show --run porcelain-0007

run_id:      porcelain-0007
status:      halted
visit_id:    v-018
node_id:     verify.intake.gate
lifecycle:   sealed
ledger_seq:  199
```

**Execution error example**

```bash
foundry check eval --check validate-manifest --workspace .
# Exit other than 0, 1, or 2 → check.errored → status execution_error
```

```text
$ foundry ledger tail --run porcelain-0007 --limit 2

seq  at                        visit  node          type               detail
───  ────────────────────────  ─────  ────────────  ─────────────────  ─────────────────────────────────────────────
  6  2026-09-24T14:38:01Z      v-008  execute.intake check.errored      validate-manifest: probe timeout
  7  2026-09-24T14:38:01Z      —      —             run.status_changed running → execution_error
```
