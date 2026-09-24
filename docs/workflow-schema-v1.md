# Foundry Workflow Schema v1

Status: **draft design definition**

This document defines the target workflow model. It is normative for the meaning of nodes, connections, visits, checks, policies, and actions. The current `factory-flow.yaml`, JSON Schema, and engine are implementation references until they conform to this definition.

---

## Charter

Define a workflow as a directed graph whose behavior can be understood from its authored registry and whose execution can be reconstructed from an append-only ledger.

The schema must make these questions answerable:

1. What work or decision does each node own?
2. Which connections may lead into and out of each node?
3. What conditions make a connection eligible?
4. What must be true before a node may start or finish?
5. Who may read, write, decide, or invoke tools while the node is active?
6. Why did a particular run proceed, pause, stop, or choose a connection?

The governing contract is:

```text
Checks evaluate reality.
Policies decide what to do.
Actions control workflow.
Gates make decisions.
Steps produce work.
```

More precisely:

- Checks are observational. They report facts without deciding flow.
- Policies map each check result to one action.
- Actions are the only imperative flow-control mechanism inside a node.
- Connections are the only declarative routing mechanism between nodes.
- A gate records one decision from a closed set of options.
- A step produces declared artifacts.

---

## Normative language

`MUST`, `MUST NOT`, `SHOULD`, and `MAY` are requirements on an authored registry or conforming engine.

Examples omit fields whose defaults are stated in this document. They are illustrative only when explicitly labeled as such.

---

## Conceptual model

```text
Workflow
  ├── entry node id
  ├── check catalog
  ├── nodes[]
  └── connections[]

Node
  ├── identity and kind (step | gate)
  ├── declared output (artifacts | decision options)
  ├── instructions or prompt
  ├── read and capability boundaries
  └── lifecycle hooks

Connection
  ├── identity
  ├── source and target node ids
  ├── seal-outcome selector
  ├── gate-decision selector
  └── optional condition

Run
  ├── mutable state snapshot
  ├── immutable event ledger
  ├── immutable artifact store
  ├── receipt files
  └── visits
```

A **node definition** describes one unit of accountability. A **visit** is one execution of that definition. Routing back to the same node creates a new visit.

A workflow carries one active visit at a time. Connections may form branches, joins, self-loops, and cycles, but they do not create concurrent tokens.

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

---

## Visits and lifecycle

A visit is one passage through a node:

```yaml
visit:
  id: v-003
  node_id: shape.examine
  kind: step
  lifecycle: opened
  outcome: null
  decision: null
  outputs: {}
  routed_from_visit_id: v-002
  routed_by_connection_id: present-to-examine
```

The visit id remains stable from admission through seal. Routing to any node, including the same node, creates a new visit id.

### Lifecycle states

| State | Meaning | Responsible actor |
|---|---|---|
| `examined` | Visit exists and is being evaluated for eligibility | Engine |
| `opened` | Work or decision interaction is in progress | Steward |
| `closed` | Steward claims the declared output is ready | Steward |
| `sealed` | Engine has accepted the visit's final disposition | Engine |

Normal progression is:

```text
admit → examined → opened → closed → sealed
```

Admission is an event, not a lifecycle state.

`closed` and `sealed` are deliberately different:

- **Closed:** the steward claims completion.
- **Sealed:** the engine has verified and accepted the claim.

### Hook timing

Hooks run at precise points:

| Hook | Current state | Purpose | Successful continuation |
|---|---|---|---|
| `on_examine` | `examined` | Determine whether this visit applies | Run `on_open` |
| `on_open` | `examined` | Verify prerequisites for steward work | Enter `opened` |
| `on_close` | `opened` | Validate the steward's close request | Enter `closed` |
| `on_seal` | `closed` | Verify output and evidence | Enter `sealed` |

An omitted or empty hook succeeds.

The steward acts only while the visit is `opened`. The engine runs all checks.

The `on_` prefix identifies these fields as lifecycle hooks rather than lifecycle states. Each hook runs when the engine reaches that lifecycle point and before the successful continuation shown above. In v1, a hook is directly an ordered list of check references; there is no nested `checks` key.

### Seal outcomes

| Outcome | Meaning |
|---|---|
| `completed` | Declared work or decision was accepted |
| `not_applicable` | The node did not apply to this visit |
| `disqualified` | Policy ruled the node out |

An outcome exists only when the visit is sealed. A failed check is not a seal outcome; policy decides whether the run halts, pauses, reopens, or seals with another outcome.

### Output accountability

`produces` is an enforceable contract, not descriptive metadata.

#### Artifact declarations

An artifact declaration is local to its producer node:

```yaml
produces:
  artifacts:
    - id: ticket
      kind: document
      uri: "run:artifacts/{visit_id}/ticket.json"
      schema: registry:schemas/ticket.schema.json
      media_type: application/json
      cardinality: one
```

| Field | Required | Meaning |
|---|:---:|---|
| `id` | yes | Logical output id, unique within the node |
| `kind` | yes | `document` or `reference` |
| `uri` | document, no | Destination template; omission requests engine-managed storage |
| `schema` | no | Registry schema used to validate structured content or reference metadata |
| `media_type` | document, no | Content media type |
| `scheme` | reference, yes | Registered immutable-reference scheme, such as `git_commit` |
| `cardinality` | no | `one` (default) or `many` |

Artifact ids may contain letters, digits, `_`, and `-`, but not `.`. Dots separate the producer node id from the artifact id in a qualified consumer reference, so this restriction keeps `shape.intake.ticket` unambiguous even though node ids may contain dots.

The declaration states what the node owes. It does not claim that the output already exists.

`one` requires exactly one published reference before completion. `many` requires one or more. Outputs that are not required for completion are evidence or logs, not declared artifacts.

`instructions` tell the steward how to create the content. The artifact protocol tells the engine how that content becomes a durable, validated output. Instructions MUST NOT invent an undeclared artifact id or final storage location.

#### Publishing artifacts

The engine exposes one logical operation:

```text
publish_artifact(visit_id, artifact_id, source)
```

The CLI MAY expose this operation as `foundry artifact publish`. The operation:

1. resolves the declaration by active visit and artifact id;
2. validates the source against the steward's capabilities and the declared artifact kind;
3. for a document, chooses the declared `uri` or allocates an engine-managed URI, then materializes immutable content there;
4. for a reference, validates and normalizes the immutable external identifier without copying external content;
5. validates `schema`, `media_type`, and `cardinality`;
6. computes a digest;
7. appends `artifact.linked`;
8. returns the concrete artifact reference.

Before work starts, the engine includes each artifact declaration, its resolved destination when known, and its publication capability in the steward context. Instructions refer to the logical artifact id; the worker does not need to rediscover the registry definition.

For a templated output such as `ticket`, the engine resolves `{visit_id}` before work starts and supplies the destination to the steward. For a dynamic output, the steward knows the artifact id but does not choose its durable path:

```yaml
produces:
  artifacts:
    - id: test-report
      kind: document
      schema: registry:schemas/test-report.schema.json
      cardinality: many
```

Each publish of `test-report` receives an engine-managed URI beneath the current run and visit. `cardinality: many` permits multiple references; omitting `uri` is what makes their final locations dynamic.

The worker instructions describe when and with what source content to invoke publication. A tool or CLI command MAY publish on the worker's behalf. The engine remains responsible for naming, validation, provenance, and ledger recording.

An immutable external result uses a reference declaration:

```yaml
produces:
  artifacts:
    - id: final-commit
      kind: reference
      scheme: git_commit
```

Publishing `final-commit` records a validated commit identifier such as `git:commit/4f91c2a`; it does not copy the repository into the artifact store. Mutable locations such as a branch name are state, not artifacts.

#### Concrete artifact references

During execution, each published output becomes a concrete reference:

```yaml
artifact:
  id: ticket
  kind: document
  producer_node_id: shape.intake
  producer_visit_id: v-001
  uri: run:artifacts/v-001/ticket.json
  schema: registry:schemas/ticket.schema.json
  media_type: application/json
  digest: sha256:8f3a...
```

An artifact instance is identified by `producer_visit_id` plus artifact `id`; repeated visits therefore produce distinct instances. A declaration used by a repeatable node MUST either include `{visit_id}` in its URI template or omit `uri` and use engine-managed storage. Artifact content is immutable after publication.

`visit.outputs` maps each artifact id to an ordered list of concrete references published by that visit. A `cardinality: one` declaration therefore has a one-item list. Before a step seals `completed`, the engine MUST verify that:

- every declaration has the number of references required by its cardinality;
- every reference names a declared artifact;
- each artifact reference exists and is readable;
- every declared schema and media type is satisfied.

This completeness check is automatic and independent of authored lifecycle checks. A node MAY also use checks to verify domain state derived from an artifact, but those checks do not replace artifact publication or completeness validation.

Pre-existing content follows the same protocol: the steward publishes it into the current visit and then requests close.

#### Consuming artifacts

A consumer identifies the producer declaration and the required lineage:

```yaml
reads:
  artifacts:
    - artifact: shape.intake.ticket
      from: nearest_sealed_ancestor
```

`shape.intake.ticket` means artifact declaration `ticket` on node `shape.intake`. `nearest_sealed_ancestor` walks the current visit's routed ancestry and selects the closest sealed producer visit with a matching artifact reference. It does not select an unrelated visit merely because that visit is newest in the run.

For example, this `reads` block can belong to `shape.examine`: the examine visit consumes the ticket produced by the nearest sealed `shape.intake` visit in its own route history.

The engine resolves these references while assembling steward context. An `on_examine` or `on_open` check still verifies any domain-specific readiness requirement.

#### Receipts are evidence

Receipts are engine-recorded evidence about how work was performed. They are not artifacts unless a downstream node consumes the receipt itself as a declared domain output.

For example, build receipts should normally be produced by the worker-completion or transition CLI operation. The worker contract and instructions define the completion payload; the CLI combines that payload with engine-owned provenance, validates the result against a schema listed under `receipts`, stores it under the run's receipt area, and appends `receipt.linked`. The builder does not invent the receipt id or durable filename. An `on_seal` check can require the expected receipt evidence without declaring `build-receipts` as a work artifact.

For a gate, the accountable output is `visit.decision`. The engine MUST reject a normal close request or completed seal unless the decision is one of `produces.options`.

The workflow is a control-flow graph, not a typed dataflow graph. A connection establishes execution order but does not bind one node's artifact to another node's input. `reads` declares accessible context; it does not prove that data exists or came from the current cycle. A node that depends on prior data MUST verify its readiness and provenance with an `on_examine` or `on_open` check.

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
  reshape-within-limit:
    when: history.count('connection.taken', loop='reshape') <= config.limits.reshape
```

The implementation flow defines `config.limits.reshape`, `config.limits.reexecute`, and `config.limits.reverify`, each defaulting to `2`. Exceeding a configured limit is handled by the check's policy, normally `escalate`.

The history query reads the authoritative ledger defined under [Run record](#run-record). A state snapshot MAY cache a derived count for display, but checks do not depend on a separately maintained loop counter.

A limit can count classified connection events or prior sealed visits, depending on the behavior being bounded. The implementation flow classifies explicit reshape and re-execute connections. Its re-verify check instead counts prior sealed `verify.intake` visits when the commit gate is examined. That count is zero before the first verification, so `config.limits.reverify` limits additional verification passes without misclassifying the initial pass as a retry.

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

---

## Read and capability boundaries

`reads` declares the context supplied to the steward. `allow` declares what the steward may change or invoke. Checks are engine-owned and do not inherit steward write capabilities.

### Defaults

| Field | Default |
|---|---|
| `reads.config` | `[]` |
| `reads.state` | `[]` |
| `reads.files` | `[]` |
| `reads.artifacts` | `[]` |
| `allow.state` | `[]` beyond implicit node scope |
| `allow.files.write` | `[]` |
| `allow.cli` | `["transition"]` for steps, including terminal steps |
| `allow.cli` on gates | `[]`; recording a decision requests close |
| `allow.agents` | `[]` beyond the bound worker |
| `allow.user.ask` | `false` |
| `allow.user.decide` | `true` only when `kind: gate` and `decider: user`; otherwise `false` |
| `lifecycle` | all hooks present as empty lists |
| `context_budget` | engine default |

The engine grants the active steward write access to `state.nodes.<node_id>.*`. Authors list only additional domain-state paths under `allow.state`.

`transition` lets a steward request close. It does not permit selection of a destination or bypass checks.

`worker` authorizes its bound worker. `allow.agents` lists only additional workers the steward may launch.

All `reads` and `allow` lists contain unique strings. State entries are state paths; file entries use the path grammar below; CLI and agent entries are registered capability ids.

`worker` requires exactly `prompt`, `contract`, and `mode`. Prompt and contract paths MUST resolve to registry files. `receipts` is either one receipt-schema path or a non-empty unique list of receipt-schema paths, and every path MUST resolve. Artifact ids and decision options are non-empty strings unique within their node.

### Worker context budget

`context_budget` bounds generated worker context:

```yaml
context_budget:
  max_input_chars: 24000
  max_summary_chars: 4000
```

Both values MUST be positive integers. The engine default applies when the field is omitted.

---

## Paths

Every file reference uses an explicit root:

| Prefix | Root |
|---|---|
| `registry:` | Flow bundle |
| `run:` | Current run directory |
| `workspace:` | Application repository |

Bare file paths are invalid.

Artifact URI templates MAY contain `{visit_id}`. A path in the producing node's `allow.files.write` MAY contain the same template only when it exactly matches a declared artifact destination. The engine resolves both occurrences to the same visit-scoped path before steward work begins. Other path fields MUST NOT contain template placeholders.

---

## Registry document

```yaml
version: 2
state_schema: registry:schemas/factory-run-state.schema.json

flow:
  id: implementation
  entry: shape.intake

  checks:
    repository-exists:
      path: workspace:.
    ticket-artifact-published:
      when: history.count('artifact.linked', visit_id=visit.id, artifact_id='ticket') == 1
    review-enabled:
      when: config.review.enabled
  nodes:
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
      reads:
        config: [workspace]
        state: [ticket]
      allow:
        state: [ticket, run_slug]
        files:
          write: ["run:artifacts/{visit_id}/ticket.json"]
        cli: [app.validate, artifact.publish, transition]
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

    - id: acceptance-review
      kind: gate
      title: Decide whether the implementation is acceptable
      decider: user
      produces:
        options: [approve, needs_changes]
      prompt: registry:prompts/acceptance-review.md

    - id: verify.complete
      kind: step
      title: Record successful completion
      terminal: true
      produces:
        artifacts: []
      instructions: registry:steps/verify-complete.md

  connections:
    - id: intake-to-review
      from: shape.intake
      to: acceptance-review
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
      to: shape.intake
      on:
        outcomes: [completed]
        decisions: [needs_changes]
```

Authored YAML SHOULD omit empty fields and values equal to documented defaults.

---

## Run record

The run has four complementary forms of persistence:

| Persistence | Responsibility |
|---|---|
| Event ledger | Authoritative sequence of workflow events |
| State snapshot | Mutable domain data and fast resume position |
| Artifact store | Immutable, per-visit documents and normalized external references |
| Receipt files | Authoritative worker outputs and evidence |

The ledger is append-only. State may summarize current position or mirror a current artifact, but it is not the audit source of truth. Artifact and receipt content remains in their stores; ledger events link each immutable item to its producing visit.

### Run status and outcome

The durable run status is one of:

| Status | Meaning | May resume? |
|---|---|:---:|
| `running` | A visit is active | yes |
| `paused` | An escalation awaits resolution | through escalation resolution |
| `halted` | Policy intentionally stopped execution | only through an explicit operator resume |
| `definition_error` | The registry or routing result is invalid | no; correct the definition |
| `execution_error` | A check or engine operation could not execute | only through an explicit operator retry |
| `completed` | A terminal visit sealed | no |

A completed run records a final outcome equal to the terminal visit's outcome: `completed`, `not_applicable`, or `disqualified`.

Every status change MUST append `run.status_changed`. A final terminal seal MUST append `run.completed` after `visit.sealed`. A halt, definition error, or execution error MUST be durable before control returns to the caller.

### Core ledger event

```yaml
seq: 42
at: 2026-09-23T22:01:04Z
run_id: run-2026-09-23-abc
visit_id: v-003
node_id: acceptance-review
type: connection.taken
payload:
  connection_id: review-approved
  to_node_id: verify.complete
```

`seq` is one-based and strictly increasing within a run. Events are immutable after append.

### Required event types

| Type | Required payload | Meaning |
|---|---|---|
| `visit.admitted` | source visit and connection ids, nullable for entry | A visit was created |
| `lifecycle.changed` | `from`, `to` | Visit lifecycle changed |
| `check.recorded` | hook, check id, result, output | A check observed reality |
| `check.errored` | hook, check id, error | A check could not be evaluated |
| `policy.applied` | check id, result, action, reason | A policy selected an action |
| `artifact.linked` | artifact id, producer visit id, URI, schema, media type, digest | A declared output was published |
| `visit.sealed` | outcome, reason, decision when present | A visit reached final disposition |
| `connection.taken` | connection id, target node id, optional loop classification | Routing selected one connection |
| `receipt.linked` | receipt id, path, schema | Evidence was attached |
| `gate.presented` | options, prompt reference | A gate was presented |
| `gate.resolved` | decision | A gate decision was recorded |
| `escalation.raised` | check id, reason | Execution paused |
| `escalation.resolved` | resolution, operator | Execution resumed or halted |
| `run.status_changed` | prior status, new status, reason | Durable run status changed |
| `run.completed` | terminal visit id and final outcome | The run ended at a terminal node |

Implementations MAY add event types, but MUST NOT change the meaning of these types.

For `receipt.linked`, `schema` is the full registry path declared in the node's `receipts` list, such as `registry:schemas/intake-receipt.schema.json`. Checks compare that canonical value rather than a schema basename.

### Event ordering

The engine MUST append events in this order:

1. `connection.taken` before the target `visit.admitted`;
2. `visit.admitted` before the visit's first `lifecycle.changed`;
3. `gate.presented` before `gate.resolved`;
4. `gate.resolved`, `artifact.linked`, and `receipt.linked` before the close request they support;
5. `check.recorded` before `policy.applied`;
6. `lifecycle.changed` to `sealed` before `visit.sealed`;
7. `visit.sealed` before `connection.taken` or `run.completed`;
8. `run.status_changed` before execution returns control because of a pause, halt, or error.

The engine MUST append the event before updating its state snapshot. It treats both writes as one logical operation; if a process stops between them, resume rebuilds the snapshot from the authoritative ledger.

---

## Engine procedure

```text
enter(node_id, source_visit_id, connection_id):
  visit = new Visit(node_id, lifecycle=null)
  append visit.admitted
  set_lifecycle(examined)

  if run_hook(on_examine) does not proceed: return
  if run_hook(on_open) does not proceed: return

  set_lifecycle(opened)
  if node is gate:
    append gate.presented
    authorized decider records a declared decision
    append gate.resolved
    close_request(visit)
  else:
    steward performs work, publishes outputs, and requests close

close_request(visit):
  require lifecycle == opened
  if run_hook(on_close) does not proceed: return
  verify declared output is complete
  set_lifecycle(closed)
  if run_hook(on_seal) does not proceed: return
  seal visit as completed

run_hook(hook):
  for check in declaration order:
    result = evaluate check
    append check.recorded
    action = explicit policy or default policy
    append policy.applied
    perform action
    if action stops the hook: return action disposition
  return proceed

seal(visit, outcome, reason=null):
  set_lifecycle(sealed)
  append visit.sealed
  if node is terminal:
    set run status completed
    append run.completed
  else:
    select exactly one eligible connection
    append connection.taken
    enter connection.to with a new visit id

set_lifecycle(to):
  append lifecycle.changed(visit.lifecycle → to)
  update visit lifecycle in the same atomic operation
```

No routing occurs before seal.

---

## Expression language

The optional top-level `expression` object declares the expression capabilities required by a registry document:

```yaml
expression:
  namespaces: [config, state, visit, history]
  operators: ["!", "&&", "||", "==", "!=", "<", "<=", ">", ">=", in]
```

When present, every namespace and operator used by a check or connection condition MUST be declared. An engine MUST reject a registry whose declared capabilities it does not support. Omission requests only the minimum language defined by this specification.

Available namespaces:

- `config.*` — immutable run configuration;
- `state.*` — current mutable domain-state snapshot;
- `visit.*` — current visit snapshot;
- `history.*` — append-only ledger queries.

Required operators:

```text
!  &&  ||  ==  !=  <  <=  >  >=  in  ( )
```

Required literals are booleans, null, strings, numbers, and list literals.

The minimum grammar is:

```text
expression     = or_expression ;
or_expression = and_expression, { "||", and_expression } ;
and_expression = comparison, { "&&", comparison } ;
comparison     = unary, [ ("==" | "!=" | "<" | "<=" | ">" | ">=" | "in"), unary ] ;
unary          = [ "!" ], postfix ;
postfix        = atom, { ".", identifier | "(", [ arguments ], ")" } ;
atom           = literal | identifier | list | "(", expression, ")" ;
arguments      = argument, { ",", argument } ;
argument       = [ identifier, "=" ], expression ;
list           = "[", [ expression, { ",", expression } ], "]" ;
literal        = "true" | "false" | "null" | string | number ;
```

Strings MAY use single or double quotes. The single `=` token is valid only between a named function argument and its value; equality uses `==`.

Required history functions:

| Function | Result |
|---|---|
| `history.count(event_type, filters...)` | Number of matching events |
| `history.last(event_type, filters...)` | Most recent matching event or `null` |
| `history.events(event_type, filters...)` | Matching events in sequence order |
| `history.visits(node_id)` | Visit ids for a node in admission order |

Expression evaluation MUST be side-effect free. Unknown names, invalid types, or evaluation failures are errors; they do not coerce to `false`.

Connection conditions evaluate after seal and can read the sealed visit's `outcome` and `decision`.

History `event_type` is an exact string such as `'visit.sealed'`. A named filter matches an event-envelope field when its name is one of `seq`, `at`, `run_id`, `visit_id`, `node_id`, or `type`; all other filter names match payload fields. `payload.<name>` MAY be used to make payload access explicit. A missing field does not match. Projecting a field from `null` is an evaluation error; authors MUST compare a nullable function result to `null` before projection.

---

## Validation

Validation has two layers.

### Structural validation

JSON Schema validates:

- required fields and primitive types;
- closed field sets;
- enum values;
- check body shape;
- ordered lifecycle hook lists and check-reference shape;
- policy and action shape;
- artifact declaration and artifact-read shape;
- node, connection, worker, and capability object shape.

### Semantic validation

`flow validate` validates relationships JSON Schema cannot fully express:

- unique ids;
- valid entry, check, node, and connection references;
- entry reachability and a structural path from every node to a terminal node;
- node-kind and output compatibility;
- artifact-id uniqueness, URI-template validity, and completed-output evidence;
- artifact schema references, cardinality, consumer references, and ancestry selectors;
- gate decider and capability compatibility;
- gate option and connection-decision compatibility;
- non-empty, unique connection selectors and valid selector values;
- action validity for each hook;
- required reasons;
- expression parsing and namespace use;
- path roots;
- path-template use and exact correspondence between a templated artifact URI and its producing node's write capability;
- exactly one body per check;
- no outgoing connections from terminal nodes;
- at least one outgoing connection from non-terminal nodes;
- statically detectable missing or overlapping routes.

The engine repeats safety-critical semantic checks at runtime, especially exactly-one connection selection.

---

## Schema guarantees

This model can describe:

- artifact-producing work nodes;
- stateful decision gates;
- conditional branches;
- decision branches;
- cycles and self-loops;
- cross-node repair loops;
- merge points in a single-token graph;
- pre-work eligibility and prerequisite checks;
- post-work verification and same-visit correction;
- terminal completion;
- auditable pause, halt, skip, and disqualification behavior.

It intentionally defines a single active visit. Therefore, a connection never means fan-out, parallel execution, event subscription, or synchronization. Those meanings MUST NOT be inferred from multiple outgoing or incoming connections.

The model has no subflow call/return construct and no automatic retry action. Same-visit correction uses `reopen`; cross-node rework uses a connection cycle; operator-directed re-evaluation uses escalation resolution `retry`.
