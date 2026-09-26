# escalation

Status: **draft capability spec**

The `foundry escalation` command group surfaces and resolves operator escalations when a check policy selects `escalate`. Escalation pauses the run (`status: paused`) per [control-plane.md](../workflow-schema-v1/control-plane.md). Resolutions are `accept`, `retry`, or `halt`; each appends `escalation.resolved` after the raising `escalation.raised` event in [run-record.md](../workflow-schema-v1/run-record.md).

---

## show

### Purpose

Return the active escalation context: triggering check, hook, visit, reason, and available resolutions.

### Who invokes

| Actor | When |
|---|---|
| operator | Run is `paused`; decide next action |
| steward | Display blocked reason in chat (read-only) |
| eval | Assert escalation payload shape |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry escalation show --run run-2026-09-24-porcelain-003 --json
```

### Sample JSON result

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "status": "paused",
  "escalation": {
    "raised_at_seq": 34,
    "visit_id": "v-012",
    "node_id": "execute.repair.limit.gate",
    "hook": "on_examine",
    "check_id": "repair-within-limit",
    "reason": "Repair loop limit reached",
    "resolutions": ["accept", "retry", "halt"]
  }
}
```

### Ledger events appended

None (read-only).

### Related factory-flow.yaml nodes/checks

Checks with `on_fail: action: escalate`:

| Check | Node | Reason |
|---|---|---|
| `repair-within-limit` | `execute.repair.limit.gate` | Repair loop limit reached |
| `reverify-within-limit` | `execute.commit.gate` | Re-verify loop limit reached |

### Cross-links

- [cli-escalation.md](cli-escalation.md) — `resolve`
- [cli-run.md](cli-run.md) — `show` when `status` is `paused`
- [control-plane.md](../workflow-schema-v1/control-plane.md) — escalation action semantics

---

## resolve

### Purpose

Record the operator's escalation resolution and resume or halt execution.

### Who invokes

| Actor | When |
|---|---|
| operator | After reviewing a paused run |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--resolution` | yes | `accept` \| `retry` \| `halt` |
| `--operator` | no | Operator identity (default: authenticated user) |
| `--reason` | no | Optional note (required when `--resolution halt`) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry escalation resolve --run run-2026-09-24-porcelain-003 --resolution retry --operator lynn --json
```

### Sample JSON result (`retry`)

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "prior_status": "paused",
  "status": "running",
  "resolution": "retry",
  "operator": "lynn",
  "resume_at": {
    "visit_id": "v-012",
    "node_id": "execute.repair.limit.gate",
    "hook": "on_examine",
    "check_id": "repair-within-limit"
  }
}
```

### Sample JSON result (`halt`)

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "prior_status": "paused",
  "status": "halted",
  "resolution": "halt",
  "operator": "lynn",
  "reason": "Loop limit exceeded; manual reshape required."
}
```

### Resolution effects

| Resolution | Run status | Execution |
|---|---|---|
| `accept` | `running` | Treat escalation as `continue`; proceed past the check |
| `retry` | `running` | Re-evaluate the same check at the same hook position |
| `halt` | `halted` | Stop without sealing; requires [cli-run.md](cli-run.md) `recover` to resume |

### Ledger events appended

| Order | Event |
|---|---|
| 1 | `escalation.raised` (already present at pause) |
| 2 | `escalation.resolved` with `resolution`, `operator` |
| 3 | `run.status_changed` (`paused` → `running` or `halted`) |
| 4+ | On `accept`/`retry`: subsequent `check.recorded`, `policy.applied` as hook resumes |

### Related factory-flow.yaml nodes/checks

Same escalate sources as `show`. Default loop limits (`config.limits.repair`, `reverify` = 2) per [control-plane.md](../workflow-schema-v1/control-plane.md).

### Cross-links

- [cli-run.md](cli-run.md) — `recover` after `halt` resolution or policy halt
- [cli-ledger.md](cli-ledger.md) — audit `escalation.*` event pair
- [cli-gate.md](cli-gate.md) — `execute.commit.gate` may raise `reverify-within-limit`
