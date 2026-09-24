# Graph

This document defines [graph invariants](#graph-invariants), [nodes](#nodes) (step, gate, terminal), and [connections](#connections). See [capabilities.md](capabilities.md) for `reads` and `allow` field semantics, [artifacts.md](artifacts.md) for `produces`, [visits-lifecycle.md](visits-lifecycle.md) for lifecycle hooks, and [control-plane.md](control-plane.md) for check references in hooks. A full integrated example is in [registry.md](registry.md).

---

## Graph invariants

A valid workflow MUST satisfy all of these rules:

1. Node ids are unique within the node namespace, connection ids within the connection namespace, and check ids within the check namespace.
2. `flow.entry` references an existing node.
3. Every connection `from` and `to` references an existing node.
4. Every node is reachable from `flow.entry`.
5. At least one reachable node is terminal.
6. Every node has a structural path to at least one terminal node.
7. A terminal node has no outgoing connections.
8. A non-terminal node has at least one outgoing connection.
9. A sealed non-terminal visit selects exactly one eligible connection.
10. A step declares artifact output; a gate declares decision output.
11. Every referenced check exists in the flow check catalog.
12. Cross-field and graph rules are enforced by semantic validation in addition to JSON Schema validation.

Cycles are valid.

A node with multiple incoming connections is a merge point, not a synchronization barrier. Because v1 has one active visit, there are no parallel branches to join.

---

## Nodes

All nodes share the same lifecycle, checks, policy behavior, capability boundaries, and audit rules. `kind` changes what the node produces and how its steward interacts.

### Common fields

| Field | Required | Meaning |
|---|:---:|---|
| `id` | yes | Stable node identifier within the flow |
| `kind` | yes | `step` or `gate` |
| `title` | yes | Short operator-facing description |
| `produces` | yes | Declared artifact outputs or decision options |
| `terminal` | no | Ends the run after any seal; default `false` |
| `instructions` | step | Registry path to steward instructions |
| `prompt` | gate | Prompt presented to the decision maker |
| `decider` | gate | Actor allowed to record the decision: `user`, `worker`, or `engine` |
| `reads` | no | Declared configuration, state, and file inputs |
| `allow` | no | Declared write and invocation capabilities |
| `lifecycle` | no | Checks and policies at lifecycle hooks |
| `worker` | no | Bound worker prompt, contract, and mode |
| `receipts` | no | Evidence receipt schemas the engine may record for the node |
| `context_budget` | no | Maximum input and summary sizes supplied to a worker |

Node ids are opaque identifiers. Dots MAY express a naming convention such as `phase.activity`, but they do not create hierarchy or imply connections.

### Step

A step produces work artifacts.

```yaml
- id: shape.intake
  kind: step
  title: Validate and normalize the work request
  produces:
    artifacts:
      - id: ticket
        kind: document
        uri: "run:artifacts/{visit_id}/ticket.json"
        schema: registry:schemas/ticket.schema.json
        media_type: application/json
  instructions: registry:steps/shape-intake.md
  lifecycle:
    on_open:
      - check: repository-exists
    on_seal:
      - check: ticket-artifact-published
        on_fail:
          action: reopen
          reason: Ticket artifact is missing
  worker:
    prompt: registry:agents/intake-checker.md
    contract: registry:contracts/intake-checker.yaml
    mode: shape
  receipts:
    - registry:schemas/intake-receipt.schema.json
```

A step declares `produces.artifacts`. The list MAY be empty for a terminal no-op step, but a non-terminal work step SHOULD declare at least one accountable output.

### Gate

A gate produces one decision. It may involve a human, an agent, or another stateful decision maker. Checks on the gate remain stateless and observational.

```yaml
- id: acceptance-review
  kind: gate
  title: Decide whether the implementation is acceptable
  decider: user
  produces:
    options: [approve, reject, needs_changes]
  prompt: registry:prompts/acceptance-review.md
```

A gate MUST:

- declare at least one unique `produces.options` value;
- record exactly one declared option in `visit.decision` before sealing `completed`;
- set `decider: user` and `allow.user.decide: true` for a user decision; or
- set `decider: worker`, bind a `worker`, and leave `allow.user.decide: false` for a worker decision; or
- set `decider: engine` for a machine gate or an engine operation that records the decision.

A one-option gate is an acknowledgment or externally triggered handoff rather than a branch. It remains a gate because the run pauses until that option is recorded.

A gate does not contain a target map. Its possible destinations are visible in the workflow's `connections`.

Recording a valid decision constitutes the gate steward's close request. A gate sealed `not_applicable` or `disqualified` has no decision.

### Terminal nodes

`terminal: true` means any seal ends the run. It does not bypass lifecycle checks.

A terminal node:

- MUST have no outgoing connections;
- MAY be a step or a gate;
- ends the run only after it seals.

A terminal step uses the same `transition` close request as any other step. `transition` requests lifecycle progress; it never means routing.

---

## Connections

Connections are the complete routing definition. There is no separate gate outcome map and no node-local target override.

```yaml
connections:
  - id: intake-to-examine
    from: shape.intake
    to: shape.examine
    on:
      outcomes: [completed, not_applicable]

  - id: review-approved
    from: acceptance-review
    to: verify.complete
    on:
      outcomes: [completed]
      decisions: [approve]

  - id: review-needs-changes
    from: acceptance-review
    to: execute.build
    on:
      outcomes: [completed]
      decisions: [reject, needs_changes]
    when: state.feature_branch != null
```

### Connection fields

| Field | Required | Meaning |
|---|:---:|---|
| `id` | yes | Stable identity used by validation and ledger events |
| `from` | yes | Source node id |
| `to` | yes | Target node id |
| `on.outcomes` | no | Eligible visit seal outcomes |
| `on.decisions` | no | Eligible gate decisions |
| `loop` | no | History classification copied to `connection.taken`; does not affect selection |
| `when` | no | Additional boolean expression evaluated after seal |

Defaults:

- omitted `on` is equivalent to an empty `on` object;
- omitted `on.outcomes` means all routable outcomes;
- omitted `on.decisions` imposes no decision constraint and also matches a visit with no decision;
- omitted `when` means `true`.

The routable outcomes are `completed`, `not_applicable`, and `disqualified`.

`on.decisions`:

- is valid only when `from` references a gate;
- MUST contain only options declared by that gate;
- is matched against the sealed visit's decision.

Selector arrays MUST be non-empty and contain unique values. `on.outcomes` MUST contain only routable outcomes. A connection condition MUST evaluate to a boolean; `null` or an evaluation failure changes the run to `definition_error` because the graph cannot select a route safely.

### Selection

After a non-terminal visit seals, the engine:

1. finds connections whose `from` equals the sealed node id;
2. filters them by `on.outcomes`;
3. for gates, filters them by `on.decisions`;
4. evaluates `when` for the remaining connections;
5. requires exactly one eligible connection;
6. appends `connection.taken`, including the connection's `loop` classification when present;
7. creates a new visit for the target node.

Zero eligible connections or multiple eligible connections change the run to `definition_error`. The engine MUST NOT create another visit.

There is no priority rule. Overlapping connections are an authoring error rather than an implicit preference.

### Branches, loops, and merge points

- **Branch:** multiple outgoing connections with mutually exclusive selectors or conditions.
- **Gate branch:** outgoing connections partition the gate's declared decisions.
- **Loop:** a connection targets an earlier node or its own source node.
- **Merge point:** multiple connections target the same node.
- **Terminal:** a sealed terminal node ends the run without selecting a connection.

The semantic validator MUST prove complete, non-overlapping route coverage when selectors and unconditional connections make that possible. Conditions based on mutable state require runtime enforcement of the exactly-one rule.

For every seal outcome and gate decision that an authored policy can produce, the author MUST provide exactly one possible route. The validator MUST enforce this whenever the policy and selectors make the route set statically knowable.
