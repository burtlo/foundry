# Command-bodied checks and the flow check catalog

Status: **design reference** — explains why `flow.checks` uses catalog indirection for `command:` bodies, how probe tokens map to CLI argv, and who owns each layer. Complements [README.md](README.md) (POC import) and [check-lookup-cli.md](check-lookup-cli.md) (Path A′ lookup). Normative behavior: [control-plane.md](../workflow-schema-v1/control-plane.md), [cli-check.md](../cli-v1/cli-check.md).

---

## Purpose

Workflow schema v1 treats **checks** as observational facts and **policies** as the response to those facts. Command-bodied checks (`command: validate_manifest`) look like unnecessary indirection next to a bare CLI invocation (`foundry app validate`). This document defends that design: what it buys, how it differs from steward capabilities, how it evolved from the PoC, and where the probe registry will live when the CLI is built.

**Audience:** flow authors, engine/CLI implementers, steward command authors (`/craft-*`), and anyone porting POC intake patterns.

---

## Governing contract

From [workflow-schema-v1 README](../workflow-schema-v1/README.md):

```text
Checks evaluate reality.
Policies decide what to do.
Actions control workflow.
```

A check never picks a route, mutates state, or returns an action. A **policy** on the hook (`on_pass`, `on_fail`, `on_not_applicable`) maps the check result to one action (`continue`, `halt`, `escalate`, `reopen`, …). Command-bodied checks are one of three ways to observe reality; they are not a separate “CLI hook” mechanism.

---

## Check catalog vs hook references

The flow registry has one in-flow catalog: `flow.checks`. Each entry has exactly one body:

| Body | Evaluator | Example |
|------|-----------|---------|
| `when` | Engine expression | `approved-ac-recorded` |
| `command` | Read-only CLI probe | `validate-manifest` |
| `path` | Path existence test | *(none in implementation flow today)* |

**Inline check bodies are not allowed.** Hooks reference catalog ids only:

```yaml
# Catalog (flow.checks)
validate-manifest:
  command: validate_manifest

# Hook (node lifecycle)
lifecycle:
  on_open:
    - check: validate-manifest
      # optional policy overrides; defaults apply when omitted
```

Default policies ([control-plane.md](../workflow-schema-v1/control-plane.md)):

| Result | Default action |
|--------|----------------|
| `pass` | `continue` |
| `fail` | `halt` |
| `not_applicable` | `continue` |

Command probes map exit codes: `0` → pass, `1` → fail, `2` → not_applicable. Any other exit, timeout, or start failure is `check.errored` (not a policy input).

---

## Why not bare CLI in the flow YAML?

You could imagine:

```yaml
on_open:
  - run: foundry app validate --workspace workspace:.
```

v1 deliberately avoids that.

### Separation of observation and consequence

Bare argv conflates “what is true?” with “what do we do?”. The catalog holds the **logical check**; the hook holds **policy** (e.g. `on_fail: reopen` on `on_seal` vs default `halt` on `on_open`). The same catalog entry can appear on multiple hooks with different policies.

### One hook shape for all check types

`when`, `command`, and `path` checks all surface as `- check: <id>`. That yields uniform ledger events (`check.recorded`), intake receipt `checks[].id` vocabulary, and eval harness entry points — without a parallel “expression hook” vs “shell hook” model.

### Security and capability boundaries

[capabilities.md](../workflow-schema-v1/capabilities.md):

> Checks are engine-owned and do not inherit steward write capabilities.

Flow YAML must not embed arbitrary shell. The `command:` value is a **registered probe token** the engine resolves — same trust model as `when` expressions (engine-evaluated only). Stewards invoke only ids listed under `allow.cli` for the active node.

### Implementation can change without rewriting the graph

Probe argv, flags, and composite orchestration (see `validate-verify-context`) live in the engine/CLI. The flow keeps stable check ids for audit either way.

### The flow stays declarative

`factory-flow.yaml` describes accountability (nodes, connections, produces, hooks). It is not an executable script. Check definitions belong in the catalog; routing belongs in connections; bulk instructions belong in `registry:` files.

---

## Three naming layers (do not collapse them)

| Layer | Example | Role |
|-------|---------|------|
| Check id (kebab-case) | `validate-manifest` | Hooks, ledger, intake receipts, `check eval --check` |
| Command body (snake_case) | `validate_manifest` | Token in `flow.checks` catalog entry |
| CLI argv | `foundry app validate` | What the engine runs (probe implementation) |
| Capability id (dot notation) | `app.validate` | Steward permission when listed in `allow.cli` |

They name the same manifest-validation probe at different boundaries. The check id is **flow vocabulary**; argv is **implementation**; capability id is **steward permission** (optional per node).

`foundry cli resolve --capability app.validate` and `foundry check eval --check validate-manifest` can target the same underlying probe; only the engine runs checks at lifecycle hooks unless a node explicitly grants the steward the capability.

---

## Who owns what

| Concern | Owner | Location today |
|---------|--------|----------------|
| Check exists, body type, `when` text | Flow author | `flow.checks` in `factory-flow.yaml` |
| Which hooks reference a check, per-hook policy | Flow author | `lifecycle` on each node |
| Probe token → argv, flags, exit semantics | Engine / CLI | [cli-check.md](../cli-v1/cli-check.md) catalog table; future probe registry |
| Evaluation, ledger, lifecycle | Engine | [engine.md](../workflow-schema-v1/engine.md) |
| Voluntary steward CLI | Node `allow.cli` | Per-node in `factory-flow.yaml` |

The YAML owns **what must be true**. The engine owns **how it is observed** and **when progress is blocked**. That split is intentional: composite probes, argv refactors, and read-only enforcement stay out of the graph file.

---

## PoC → v1: from stubs to engine enforcement

In the PoC, intake check names on `actions.on_enter` were **stubs**: the engine recorded `required_intake_checks` in state but did **not** run the CLI. The steward/worker ran probes during the step and sealed pass/fail in the intake receipt. Enforcement was soft.

v1 moves execution to lifecycle hooks (`on_examine`, `on_open`, `on_close`, `on_seal`):

1. Engine evaluates checks in order.
2. Appends `check.recorded` then `policy.applied`.
3. Only then opens steward work (`opened`) or applies halt/escalate/skip.

Intake receipts still carry `checks[]`, but on **Path B** the steward assembles them from ledger `check.recorded` events for the visit — not from re-running probes or from worker-returned check lists. See [README.md](README.md) §2.

PoC heritage: named tokens like `validate_manifest` survived. v1 heritage: engine-owned, mandatory, ledger-first evaluation.

---

## Runtime path (when CLI exists)

On admission (e.g. `foundry run create` admitting `shape.intake`):

```text
visit.admitted → lifecycle: examined
run_hook(on_examine)   # empty on first shape.intake → succeeds
run_hook(on_open)      # validate-manifest → foundry app validate (probe)
lifecycle: opened      # only if policies allow
```

For each check in hook order ([engine.md](../workflow-schema-v1/engine.md)):

1. Evaluate (expression, probe, or path test).
2. Append `check.recorded` (includes probe output when applicable).
3. Resolve policy (explicit or default).
4. Append `policy.applied`.
5. Perform action; stop hook if action requires it.

Stewards do **not** run `validate-manifest` on `shape.intake` — it is not in that node’s `allow.cli`. Direct `foundry app validate` is for operators, eval fixtures, or nodes that grant `app.validate`.

---

## Command-bodied checks in the implementation flow

Five catalog entries use `command:` (of ~27 total checks). All others use `when` expressions.

| Check id | Command body | CLI probe (draft) | Nodes (hook) |
|----------|--------------|-------------------|--------------|
| `validate-manifest` | `validate_manifest` | `foundry app validate` | `shape.intake`, `execute.intake`, `verify.intake` (`on_open`) |
| `validate-git-clean-execute` | `validate_git_clean_execute` | `foundry git clean-check` | `execute.intake` (`on_open`) |
| `validate-verify-context` | `validate_verify_context` | Composite probe (manifest, branch, commit, graph, receipts) | `verify.intake` (`on_open`) |
| `ensure-execution-graph-reference` | `ensure_execution_graph_reference` | `foundry graph ensure-reference` | `execute.plan` (`on_open`) |
| `validate-build-exit` | `validate_build_exit` | `foundry build validate-exit` | `execute.build` (`on_seal`) |

Authoritative mapping: [cli-check.md § Catalog check mapping](../cli-v1/cli-check.md). Introspection (draft): `foundry check describe --check validate-manifest` — [check-lookup-cli.md](check-lookup-cli.md).

**Reuse example:** `validate-manifest` is defined once and referenced from three phase intakes. Without the catalog, the same probe token or argv would be duplicated across nodes, and ledger/receipt ids would drift.

**Expression reuse example:** `agent-receipt-sealed` is referenced from many nodes’ `on_seal` hooks with the same `when` body but node-local `on_fail: reopen` reasons.

---

## Why only one in-flow catalog?

v1 uses three reference patterns:

| Pattern | Examples |
|---------|----------|
| In-flow catalog | `flow.checks` |
| Registry file refs | `registry:nodes/…`, `registry:workers/…`, `registry:steps/…`, `registry:agents/…`, `registry:schemas/…` |
| Engine-owned tables | Probe registry, `allow.cli` → argv via `cli resolve` |

Checks earned a catalog because they are **cross-cutting**, **heavily reused**, and need **stable audit ids** across hooks, ledger, receipts, and integrity checks. Most other artifacts do not:

- **Nodes and connections** are the graph itself, not a reusable library.
- **Instructions and workers** are bulky content → external `registry:` files.
- **Artifacts** are local accountability per producer ([artifacts.md](../workflow-schema-v1/artifacts.md)).
- **Policies** are hook-contextual (same check, different `on_fail` on `on_open` vs `on_seal`).
- **Connection `when`** clauses are routing glue; they do not produce `check.recorded`.

PoC had a top-level `gates:` catalog; v1 folded gates into `kind: gate` nodes for a uniform lifecycle. Fewer YAML catalogs, not more — by unifying node kinds.

A future **`registry:probes.yaml`** (or equivalent) may formalize command-body → argv mapping currently documented only in CLI specs. That remains engine-adjacent, not flow-authored argv.

---

## Steward and worker rules (transitions)

When porting POC prompts or writing `/craft-*` commands:

| Rule | Detail |
|------|--------|
| Engine runs hook checks | Do not list catalog probes as steward steps when the hook already owns them ([gaps.md](../cli-v1/gaps.md) §2). |
| Path B intake receipts | Build `checks[]` from ledger `check.recorded` for `on_examine` + `on_open` on this visit — not from worker output. |
| Workers do not re-run catalog checks | Synthesis and judgment only; see [README.md](README.md) §2. |
| Debug without mutating | `foundry check describe` / `check show` (Path A′); not `check eval` for audit truth on a sealed visit. |

Example: `shape.intake` `on_open` runs `validate-manifest`. Steward directs the user to `/craft-init` on failure; do not `transition` past a halted visit.

---

## Related documents

| Document | Contents |
|----------|----------|
| [control-plane.md](../workflow-schema-v1/control-plane.md) | Checks, policies, actions, catalog rules |
| [visits-lifecycle.md](../workflow-schema-v1/visits-lifecycle.md) | Hook timing and steward `opened` boundary |
| [capabilities.md](../workflow-schema-v1/capabilities.md) | `reads`, `allow.cli`, engine-owned checks |
| [cli-check.md](../cli-v1/cli-check.md) | `check eval`, catalog mapping table |
| [cli-app.md](../cli-v1/cli-app.md) | `app validate` as `validate-manifest` probe |
| [docs/generated/nodes/shape.intake.md](../generated/nodes/shape.intake.md) | End-to-end sequence for first command-bodied check |
| [check-lookup-cli.md](check-lookup-cli.md) | Path A′ describe/show |
| [cli-poc-transition.md](../cli-v1/cli-poc-transition.md) | PoC → v1 CLI mapping (reference only) |
