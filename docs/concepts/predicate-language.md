# Predicate language

Status: **exploratory** — breaking change candidate; supersedes [expressions.md](expressions.md) when adopted.

Connection `when` conditions and check `when` bodies are **pure, typed boolean predicates** over a fixed **Foundry fact environment**. The language is side-effect free. Predicates read authoritative state and MAY read engine-maintained derived fields; agents MUST NOT be responsible for keeping derived values in sync with their sources.

Implementation MAY use any engine that satisfies this spec (native interpreter, CEL with extensions, etc.). The contract is the fact environment and evaluation semantics, not a particular library.

Related: [control-plane.md](control-plane.md) (check results), [graph.md](graph.md#selection) (routing), [validation.md](validation.md) (compile-time rules), [run-record.md](run-record.md) (ledger).

---

## Architectural decision

| Principle | Rule |
|---|---|
| **Pure** | Evaluation MUST NOT mutate state, ledger, files, or external systems |
| **Typed** | Every expression is type-checked at compile time against declared schemas |
| **Explicit facts** | Predicates read only `config`, `state`, `visit`, and `history` — no hidden engine globals |
| **One source of truth** | Each fact has one authoritative source. Derived values MAY exist (eval-time or materialized) but MUST NOT require an agent to keep them synchronized |
| **Errors are errors** | Parse, type, and evaluation failures MUST NOT coerce to `false` |

Checks and routing share one language and one evaluator. They differ only in how results are interpreted (see [Result interpretation](#result-interpretation)).

---

## Foundry fact environment

At evaluation time the engine builds an **activation** — a read-only snapshot of observable inputs:

```text
activation {
  config:  Map<String, Value>   // frozen run configuration
  state:   Map<String, Value>   // current domain state (state.json)
  visit:   VisitRecord           // active or just-sealed visit
  history: HistoryQuery          // pure ledger query surface
}
```

### `config.*`

Immutable for the lifetime of a run. Loaded from app manifest + Foundry defaults at run bootstrap.

### `state.*`

Mutable domain data persisted in `{run_dir}/state.json`. Types come from the flow's `state_schema` reference (see [Type environment](#type-environment)).

#### Authoritative state

Fields and collections that stewards, workers, or authorized CLI commands write directly — for example `clarifying_questions[]`, `approved_ac`, `feature_branch`. These are the **source of truth**. Predicates SHOULD prefer querying authoritative structures directly when the cost is acceptable.

#### Derived state

Values computed from authoritative state. Two forms:

| Form | Who maintains | When to use |
|---|---|---|
| **Eval-time** | Engine, on each predicate evaluation | Default. Collection expressions such as `.filter(…).size()` or `.exists(…)` over small or moderate collections |
| **Materialized** | Engine, when authoritative state changes | Optional cache when the derivation is costly (large collections, repeated history scans, cross-field aggregation) |

Materialized derived fields MUST:

1. Be declared in `state_schema` with an explicit derivation (see [open question](#open-questions) on `x-foundry-derived`);
2. Be updated only by the engine (or CLI subcommands acting as engine proxies) — never by steward `visit state patch` or worker writes;
3. Be omitted from node `allow.state` grants so agents cannot patch them;
4. Remain a pure function of authoritative state — if authoritative data changes, the derived value MUST be recomputed before the next predicate evaluation or seal.

Predicates MAY reference materialized derived scalars (e.g. `state.open_clarifying_questions_count == 0`) when declared and engine-maintained. Prefer eval-time expressions until profiling shows need for materialization.

#### Forbidden pattern: agent-synced derived

Scalar fields that duplicate authoritative data and rely on an agent to patch both the source and the copy are **not allowed**. Example: steward patches `clarifying_questions[]` and also patches `open_clarifying_questions_count` by hand. That creates drift risk and violates one source of truth regardless of whether the scalar appears in predicates.

### `visit.*`

The visit record at the point of evaluation:

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Visit id (`v-001`, …) |
| `node_id` | string | Flow node id |
| `kind` | string | `step` or `gate` |
| `lifecycle` | string | Current lifecycle state |
| `outcome` | string \| null | Seal outcome when sealed |
| `decision` | string \| null | Gate decision when present |

Connection `when` clauses evaluate after seal; `visit.outcome` and `visit.decision` reflect the sealed visit.

### `history.*`

Append-only ledger queries. Implementations MUST NOT expose raw ledger mutation or iteration with side effects.

| Function | Result type | Meaning |
|---|---|---|
| `history.count(event_type, filters…)` | int | Number of matching events |
| `history.last(event_type, filters…)` | Event \| null | Most recent match, or null |
| `history.events(event_type, filters…)` | list\<Event\> | Matches in sequence order |
| `history.visits(node_id)` | list\<string\> | Visit ids admitted for a node, in order |

**Event type** is a string literal such as `'visit.sealed'`.

**Filters** are named arguments: `node_id='shape.examine'`, `visit_id=visit.id`, `schema='registry:schemas/…'`, `loop='repair'`, etc.

A filter name matches an envelope field when it is one of `seq`, `at`, `run_id`, `visit_id`, `node_id`, or `type`. All other names match `payload` fields. `payload.<name>` MAY be used for explicit payload access.

**Event value.** `history.last(…)` returns a struct merging envelope fields with `payload` fields at the top level, so `history.last(…).outcome` and `history.last(…).decision` work after a null guard.

**Null projection.** Accessing a field on `null` is a type/evaluation error. Authors MUST compare nullable results to `null` before projection, or use optional forms where the type checker accepts them.

---

## Language surface

### Registry declaration

```yaml
expression:
  version: 2
  state_schema: registry:schemas/factory-run-state.schema.json
  namespaces: [config, state, visit, history]
  features: [collections, lambdas, history, optional_coalesce]
```

| Field | Required | Meaning |
|---|:---:|---|
| `version` | yes | Predicate language version (`2` for this spec) |
| `state_schema` | yes | JSON Schema for `state.*` typing |
| `namespaces` | yes | Allowed root namespaces |
| `features` | no | Enabled extensions; omitted features MUST NOT appear in any `when` body |

An engine MUST reject a registry whose expressions use undeclared namespaces or features.

### Literals and operators

| Kind | Syntax |
|---|---|
| Booleans | `true`, `false` |
| Null | `null` |
| Strings | `'single'` or `"double"` quoted |
| Numbers | JSON number syntax |
| Lists | `[a, b, c]` |
| Logical | `!`, `&&`, `\|\|` |
| Comparison | `==`, `!=`, `<`, `<=`, `>`, `>=` |
| Membership | `in` — `x in [1, 2, 3]` or `x in ['open', 'answered']` |
| Grouping | `( … )` |
| Member access | `.` — `state.approved_ac_version`, `q.status`, `visit.id` |

Short-circuit: `&&` and `||` MUST short-circuit.

### Collection expressions (feature: `collections`, `lambdas`)

State fields typed as `array` in `state_schema` support **collection methods**. Methods are pure; they do not modify the underlying array.

| Method | Signature | Result | Meaning |
|---|---|---|---|
| `filter` | `.filter(item, predicate)` | list | Elements where `predicate` is true |
| `exists` | `.exists(item, predicate)` | bool | Any element matches |
| `all` | `.all(item, predicate)` | bool | Every element matches (vacuous true on empty) |
| `none` | `.none(item, predicate)` | bool | No element matches |
| `count` | `.count(item, predicate)` | int | Number of matching elements |
| `size` | `.size()` | int | Length of list |
| `isEmpty` | `.isEmpty()` | bool | `size() == 0` |

**Lambda form:** `(binding, body)` where `binding` is an identifier and `body` is a boolean expression with the element in scope.

```text
collection_expr "." method "(" identifier "," expression ")"
collection_expr "." "size" "(" ")"
collection_expr "." "isEmpty" "(" ")"
```

**Receiver typing.** Collection methods MUST only be invoked on values typed as `array` (or the result of another collection method returning a list). Invoking on `null` or a non-array is a compile-time error unless optional chaining is used.

**Missing array in state.** When a state field is absent or `null` at runtime but typed as an array in schema, collection receivers MUST behave as an **empty list** for `filter`, `exists`, `all`, `none`, `count`, `size`, and `isEmpty`. This keeps routing predicates stable when a collection has not been initialized yet.

### Optional coalescing (feature: `optional_coalesce`)

When enabled:

```text
nullable_expr "?." member
nullable_expr "?." method ( … )
```

If the receiver is `null`, the whole optional chain evaluates to `null` without error. Otherwise same as non-optional access.

Optional chains are primarily for history and nullable scalars. Collection methods on missing state arrays use the empty-list rule above instead.

---

## Motivating example: open clarifying questions

**Goal.** Route from `shape.examine` to `shape.present` when no clarifying questions remain open. Authoritative source: `state.clarifying_questions[]`. Prefer eval-time predicates (no agent-maintained count):

Equivalent predicates (all valid):

```text
state.clarifying_questions.filter(q, q.status == "open").size() == 0
```

```text
!state.clarifying_questions.exists(q, q.status == "open")
```

```text
state.clarifying_questions.none(q, q.status == "open")
```

```text
state.clarifying_questions.count(q, q.status == "open") == 0
```

If profiling shows this scan is too costly at scale, the flow MAY declare `open_clarifying_questions_count` as an engine-materialized derived field (see [Derived state](#derived-state)) and route on `state.open_clarifying_questions_count == 0` instead — still forbidden as an agent-patched scalar.

**Fast lane connection** (`shape.examine` → `shape.present`):

```yaml
when: state.clarifying_questions.none(q, q.status == "open")
```

**Gate path connection** (`shape.examine` → `shape.examine.gate`):

```yaml
when: state.clarifying_questions.exists(q, q.status == "open")
```

**Check catalog equivalent:**

```yaml
checks:
  no-open-clarifying-questions:
    when: state.clarifying_questions.none(q, q.status == "open")
```

Agents patch only `clarifying_questions[]` (and other authoritative fields). The engine derives routing at seal time from the collection — or from an engine-maintained materialized count if the flow declares one.

---

## Grammar (normative sketch)

Whitespace is insignificant except inside strings. Method chains bind left-to-right.

```text
expression       = or_expr ;
or_expr          = and_expr, { "||", and_expr } ;
and_expr         = equality, { "&&", equality } ;
equality         = comparison, [ ("==" | "!="), comparison ] ;
comparison       = additive, [ ("<" | "<=" | ">" | ">="), additive ] ;
additive         = postfix ;
postfix          = primary, { postfix_op } ;
postfix_op       = "." identifier [ "(" arg_list ")" ]
                   | "." identifier
                   | "?." identifier [ "(" arg_list ")" ] ;
primary          = literal | list | lambda | namespace_ref | "(" expression ")" ;
lambda           = "(" identifier "," expression ")" ;
namespace_ref    = ("config" | "state" | "visit" | "history"), { "." identifier }, [ call ] ;
call             = "(" arg_list ")" ;
arg_list         = argument, { ",", argument } ;
argument         = [ identifier "=" ], expression ;
list             = "[", [ expression, { ",", expression } ], "]" ;
literal          = "true" | "false" | "null" | string | number ;
```

**Lambda restriction.** A `lambda` is valid only as the second argument to `filter`, `exists`, `all`, `none`, or `count`. Lambdas MUST NOT appear elsewhere.

**History calls.** `history.count`, `history.last`, `history.events`, and `history.visits` use the `history` namespace with call syntax as in v1, extended to accept collection-free lambdas only in future if ledger query filters need them (not in v2).

---

## Type environment

Compile-time typing uses:

1. **`state_schema`** — JSON Schema for `state.*` paths and collection element shapes
2. **Fixed visit schema** — fields listed under [visit.*](#visit)
3. **Config schema** — from Foundry config schema + keys referenced in the flow
4. **History function signatures** — fixed return types per [history.*](#history)

### Element field access

For `state.clarifying_questions.filter(q, q.status == "open")`, the binder `q` is typed from `state_schema` → `clarifying_questions.items`. Field access `q.status` MUST be validated against the item schema (`enum` for status: `open`, `answered`, `withdrawn`).

### Predicate result

Every check `when` and connection `when` MUST compile to a type assignable to `bool | null`. Runtime evaluation produces exactly one of:

| Value | Meaning in checks | Meaning in routing |
|---|---|---|
| `true` | pass | connection eligible |
| `false` | fail | connection not eligible |
| `null` | not_applicable | treated as not eligible |
| error | check.errored | run → definition_error |

Routing MUST require exactly one eligible connection among those matching outcome/decision; zero or many eligible connections → `definition_error`.

---

## Compile and evaluate

### Compile (`flow validate`)

For each check and connection `when` body:

1. Parse against grammar
2. Verify namespaces and features against flow `expression` declaration
3. Type-check against type environment
4. Emit a compiled predicate (opaque to authors; MAY be serialized)

Compile failures are registry errors. The flow MUST NOT be used for new runs until fixed.

### Evaluate (runtime)

```text
evaluate(compiled_predicate, activation) → bool | null | Error
```

The engine builds `activation` from the current snapshot and visit, then evaluates. No I/O beyond reading the already-loaded snapshot.

**Call sites:**

| Site | Hook |
|---|---|
| Check catalog `when` | lifecycle hooks via [control-plane.md](control-plane.md) |
| Connection `when` | post-seal routing via [graph.md](graph.md#selection) |

---

## Result interpretation

Aligned with [control-plane.md](control-plane.md):

| Body | `true` | `false` | `null` | Evaluation error |
|---|---|---|---|---|
| Check `when` | pass | fail | not_applicable | `check.errored`; run → `execution_error` |
| Connection `when` | eligible | not eligible | not eligible | run → `definition_error` |

Evaluation errors during routing occur when the graph cannot safely select a connection (including type errors and null projection on history).

---

## Additional examples

### Prior visit sealed

```text
history.last('visit.sealed', node_id='execute.intake') != null &&
history.last('visit.sealed', node_id='execute.intake').outcome == 'completed'
```

Preferred with optional chaining when feature enabled:

```text
history.last('visit.sealed', node_id='execute.intake')?.outcome == 'completed'
```

Note: optional chaining yields `null == 'completed'` → `false`, not pass. For checks requiring prior seal, use explicit null guard or a dedicated helper in a future revision.

### Approved scope freeze

```text
state.approved_ac_version >= 1
```

### Receipt sealed for active visit

```text
history.count(
  'receipt.linked',
  visit_id=visit.id,
  schema='registry:schemas/intake-receipt.schema.json'
) >= 1
```

### Code quality skipped or done

```text
!config.review.enabled ||
(
  history.last('visit.sealed', node_id='verify.code_quality') != null &&
  history.last('visit.sealed', node_id='verify.code_quality').outcome in ['completed', 'not_applicable']
)
```

### Repair limit

```text
history.count('connection.taken', loop='repair') <= config.limits.repair
```

---

## Breaking changes from v1 expressions

| v1 | v2 |
|---|---|
| `expression` without `version` | `expression.version: 2` required |
| No collection methods | `filter`, `exists`, `all`, `none`, `count`, `size`, `isEmpty` |
| Agent-synced routing scalars (e.g. steward-patched `open_clarifying_questions_count`) | Eval-time collection predicates, or engine-materialized derived fields |
| Ad hoc string-matching evaluator | Full grammar + compile pass |
| Unknown expression → false at runtime | Compile error or explicit evaluation error |
| Optional `state_schema` on flow | Required for type checking |

Migration steps for the implementation flow:

1. Add `expression.version: 2` and `features` to `factory-flow.yaml`
2. Replace agent-synced `open_clarifying_questions_count` routing with collection predicates (or engine-materialized derived fields if costly)
3. Remove `open_clarifying_questions_count` from node `allow.state` and steward patch instructions; remove from schema unless redeclared as engine-derived
4. Replace engine special cases in `routing.py` with the generic evaluator

---

## Implementation notes (non-normative)

**CEL.** [Common Expression Language](https://cel.dev) can implement this spec if Foundry registers:

- `history.count`, `history.last`, `history.events`, `history.visits` as pure functions
- List macros or extensions for `filter` / `exists` / … with lambda semantics

Authors would write CEL-compatible syntax; the examples above are intentionally CEL-shaped. A thin syntax adapter MAY accept the documented grammar and lower to CEL.

**Native interpreter.** A standalone parser + typed AST + evaluator satisfies the spec without external dependencies. Recommended when the CLI bundle must stay pure Python and syntax must match this document literally.

**Performance.** Compile once per flow version; evaluate many times per run. Collection operations on small examination arrays are O(n) with n bounded by human-scale question counts — eval-time derivation is sufficient by default. When a derivation is costly, the flow MAY declare a materialized derived field maintained by the engine; predicates then read the cache without changing the one-source-of-truth rule.

---

## Open questions

1. **`first` / `last` on collections** — useful for `state.approved_ac.first()`; defer until needed?
2. **Materialized derived fields in schema** — e.g. JSON Schema `x-foundry-derived: { expr: "…" }` for engine-maintained caches of costly predicates; ties to [Derived state](#derived-state)
3. **`history` lambdas** — filter events by payload predicate without repeating `history.last`; defer?
4. **Vacuous `all` on empty** — specified as true; confirm product intent for examination gates?

---

## Reading order

1. This document — language and fact environment
2. [control-plane.md](control-plane.md) — how check results map to actions
3. [graph.md](graph.md#selection) — connection selection
4. [validation.md](validation.md) — where compile fits in `flow validate`
5. [expressions.md](expressions.md) — superseded v1 minimal grammar (reference only)
