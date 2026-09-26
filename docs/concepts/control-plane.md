# Control plane

Checks evaluate reality. Policies decide what to do. Actions control workflow. This document defines [checks](#checks), [policies](#policies), and [actions](#actions). Lifecycle hooks that invoke checks are described in [visits-lifecycle.md](visits-lifecycle.md#hook-timing). History-backed checks read the ledger defined in [run-record.md](run-record.md). Expression syntax is in [expressions.md](expressions.md).

---

## Checks

Checks answer one question: **what is true now?**

Checks MUST be deterministic for the same observable inputs and MUST NOT mutate workflow state, files, configuration, or external systems. A command used as a check is therefore a read-only probe.

### Results

| Result | Meaning |
|---|---|
| `pass` | The condition is satisfied |
| `fail` | The condition is not satisfied |
| `not_applicable` | This check does not apply to this visit |

Result names use snake case consistently in YAML, expressions, and ledger events.

Checks never return actions or destinations.

### Check catalog

Each catalog entry has exactly one body:

| Body | Evaluation |
|---|---|
| `when` | Expression over allowed namespaces |
| `command` | Read-only Foundry CLI probe; exit `0` is `pass` |
| `path` | Test whether a registry, run, or workspace path exists |

Body results are mapped as follows:

| Body | `pass` | `fail` | `not_applicable` | Evaluation error |
|---|---|---|---|---|
| `when` | expression is `true` | expression is `false` | expression is `null` | parse error, unknown name, or non-boolean/non-null value |
| `command` | exit `0` | exit `1` | exit `2` | cannot start, timeout, signal, or any other exit |
| `path` | path exists | path does not exist | never | invalid root or inaccessible path |

An evaluation error is not a check result and does not invoke policy. The engine appends `check.errored`, changes the run to `execution_error`, and does not continue the hook.

```yaml
checks:
  repository-exists:
    path: workspace:.
  review-enabled:
    when: config.review.enabled
  manifest-valid:
    command: app.validate
```

Node hooks reference catalog checks with `check` and optionally override result policies:

```yaml
lifecycle:
  on_examine:
    - check: review-enabled
      on_fail:
        action: skip
        reason: Review is disabled
```

Inline check bodies are not allowed. A check definition belongs in the catalog; a hook item contains only its `check` reference and policy overrides.

### Check order and recording

Checks run in declaration order. For every evaluated check, the engine MUST:

1. append `check.recorded`;
2. resolve the policy for that result;
3. append `policy.applied`;
4. perform the selected action.

The check event is recorded before its action can alter execution.

### History-backed checks

Checks may compare configuration with prior run events through the `history` namespace:

```yaml
checks:
  repair-within-limit:
    when: history.count('connection.taken', loop='repair') <= config.limits.repair
```

The implementation flow defines `config.limits.repair` and `config.limits.reverify`, each defaulting to `2`. Exceeding a configured limit is handled by the check's policy, normally `escalate`. Reshape and replan/rework_execute loops are bounded by explicit user gate decisions; intake and execute entry steps do not re-check those counts. All `repair` routes converge on `execute.repair.limit.gate` before `execute.build`.

The history query reads the authoritative ledger defined under [Run record](run-record.md). A state snapshot MAY cache a derived count for display, but checks do not depend on a separately maintained loop counter.

A limit can count classified connection events or prior sealed visits, depending on the behavior being bounded. The implementation flow classifies explicit repair connections from the repair limit gate to `execute.build`. Its re-verify check instead counts prior sealed `verify.intake` visits when the commit gate is examined. That count is zero before the first verification, so `config.limits.reverify` limits additional verification passes without misclassifying the initial pass as a retry.

---

## Policies

A policy maps one check result to exactly one action:

```yaml
- check: ticket-file-present
  on_pass:
    action: continue
  on_fail:
    action: reopen
    reason: Ticket file is missing
  on_not_applicable:
    action: halt
    reason: Ticket evidence check must apply
```

The default policies are:

| Result | Default action |
|---|---|
| `pass` | `continue` |
| `fail` | `halt` |
| `not_applicable` | `continue` |

Authors omit policy fields when these defaults are correct.

A policy contains one action, not an action list. The v1 actions are flow-control operations, so sequencing several of them creates ambiguous stop and resume behavior.

---

## Actions

| Action | Effect | Valid hooks | Stops current hook? |
|---|---|---|:---:|
| `continue` | Evaluate the next check; if none remains, complete the hook | all | no |
| `satisfy` | Mark the current hook satisfied without evaluating remaining checks | all | yes |
| `skip` | Seal `not_applicable` without opening steward work | `on_examine`, `on_open` | yes |
| `reopen` | Move the same visit from `closed` to `opened` for correction | `on_seal` | yes |
| `halt` | Set run status `halted` without sealing or routing | all | yes |
| `escalate` | Set run status `paused` for an operator decision | all | yes |
| `disqualify` | Seal `disqualified` | all | yes |

`reason` is required on `skip`, `reopen`, `halt`, `escalate`, and `disqualify`.

### Early seal actions

`skip` and `disqualify` seal the current visit directly. They do not bypass audit:

1. the triggering check and policy are recorded;
2. lifecycle changes to `sealed`;
3. `visit.sealed` records the outcome and reason;
4. a non-terminal node selects a connection normally.

`skip` means the node does not apply.

If `skip` or `disqualify` seals a gate after a provisional decision was recorded, the engine clears `visit.decision` before `visit.sealed`. The earlier `gate.resolved` event remains in the ledger, so the rejected decision is still auditable.

### Reopen

`reopen` is valid only during the `on_seal` hook. It changes `closed → opened` on the same visit. No connection is selected and no new visit is created.

Cross-node repair is modeled by a connection and therefore creates a new visit.

Reopening a gate clears `visit.decision`. A new decision and `gate.resolved` event are required before the gate can request close again.

### Escalation

`escalate` pauses the run at the current check. Operator resolution MUST be recorded as one of:

- **accept** — treat the escalation as `continue`;
- **retry** — evaluate the same check again;
- **halt** — halt the run.

The registry does not encode the operator's eventual choice.

`accept` and `retry` return the run to `running` before execution resumes. `halt` changes it to `halted`. An explicit resume of a halted run returns to the same visit and hook position and MUST record the operator and reason.

### Hook action rules

JSON Schema rejects hook/action combinations that are invalid by shape. The semantic validator MUST enforce the same rules when validating a resolved flow:

- `skip` in `on_close` or `on_seal`;
- `reopen` outside `on_seal`;
- a required action without a non-empty `reason`;
- any unknown action;
- an action list in place of one action.
