# Engine node runtime profile

Status: Concept companion to [implementation-flow-runtime.md](../features/implementation-flow-runtime.md). Profile drives `classify_advance_node` and host dispatch.

## Purpose

`NodeRuntimeProfile` is the single read model for how the host treats a node today: advancement class, bound operations manifest, task binding, intake policy flags, and legacy engine gate resolver id.

## Schema

Loaded by `foundry_cli.engine.node_runtime_profile.load_node_runtime_profile(node_id, flow, foundry_bundle)`.

| Field | Type | Meaning |
|-------|------|---------|
| `node_id` | str | Flow node id |
| `advance_mode` | enum | See below |
| `operations_ref` | str \| null | `node.yaml` `operations:` ref, or `registry:nodes/<id>/operations.yaml` when that file exists and is unbound |
| `task_id` | str \| null | Agent task id when `advance_mode` is `task` (task file at `tasks/<id>.yaml`) |
| `blocked_intake` | bool | Node may transition to blocked intake wait (`execute.intake`, `verify.intake`) |
| `host_only_boundary` | bool | Advance must not leave the host at this boundary (`execute.intake`, `verify.intake`, `execute.test`) |
| `engine_gate_resolver` | str \| null | Gate node id when `nodes/<id>/gate.rules.yaml` exists (Step 10 declarative rules) |
| `task_file_exists` | bool | Filesystem: `tasks/<node_id>.yaml` |
| `operations_file_exists` | bool | Filesystem: `nodes/<node_id>/operations.yaml` |

### `advance_mode` values

| Value | Current behavior |
|-------|------------------|
| `host` | Host step: `MechanismRunner` over bound `operations.yaml` |
| `task` | Agent task + `ensure_agent_request` / task-bound advance |
| `git_mechanical` | Git/mechanical host step (`execute.branch`) |
| `gate_user` | User gate; `gate decide` / start authorization |
| `gate_engine` | Engine gate; `resolve_engine_gate_decision` evaluates `gate.rules.yaml` |
| `manual` | Reserved; not emitted by the Step 1 loader |
| `unsupported` | Operator unsupported wait for post-shape steps without host/task binding |

Resolution order matches `classify_advance_node`: gate decider → git mechanical set → host-implemented steps → task registry file → post-shape unsupported fallback.

## Sources

1. Materialized flow node (`node.yaml` via `get_node`)
2. Bundle filesystem: `tasks/`, `nodes/*/operations.yaml`, `nodes/*/gate.rules.yaml`
3. Catalog index (future): optional `runtime` section in Step 6+

## Engine gate rules (`gate.rules.yaml`)

Each engine gate (`decider: engine`) ships `nodes/<gate>/gate.rules.yaml`, evaluated by `foundry_cli.engine.gate_rules.evaluate_gate_rules`. `resolve_engine_gate_decision`:

1. Requires every `lifecycle.on_examine` check from the gate's `node.yaml` to be recorded `pass` (or a live limit check to pass). A failing check maps to `examine.fail_codes[<check>]` when declared (e.g. `REPAIR_LIMIT_EXCEEDED`), else `EVIDENCE_MISSING`.
2. Loads `evidence` (keyed by id) through `evidence.gate_evidence`:
   - `kind: receipt` (`step`, `schema`) → `sealed`, `visit_id`, `outcome`, `linked`, `missing_file`, `receipt_id`, `status`, `commands_count`, `commands_all_pass`, `commands_any_failed`
   - `kind: artifact` (`step`, `artifact_id`, `fields` with optional `transform: trim_lower`) → `sealed`, `visit_id`, `linked`, `missing_file`, plus declared fields
   - `kind: state` (`field`) → `present`, `value`
3. Evaluates `derive` expressions in order (available as `derived.<name>`).
4. Walks `rules` in order; the first rule whose `when` holds (omitted `when` = always) wins:
   - `decision: <option>` or `decision_from: <expr>` → `ok`, `rule_id` `<gate>/<id>` (or a `rule_id` template using `{decision}`), `evidence_refs` from receipt ids unless `evidence_refs: false`
   - `reject: <code>` + `message` template (`{evidence.x.y!r}`) → fail-closed outcome

Expressions use the typed evaluator (`expressions.evaluate_condition`) with `evidence` and `derived` as extra roots alongside `state`, `config`, and `history`. The decision must still be in the gate's `produces.options`.
