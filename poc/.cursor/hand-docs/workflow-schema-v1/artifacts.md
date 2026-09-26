# Artifacts and output accountability

This document covers artifact declarations, [publishing](#publishing-artifacts), [consuming](#consuming-artifacts), and [receipts vs artifacts](#receipts-are-evidence). Node field definitions appear in [graph.md](graph.md#nodes); capability boundaries in [capabilities.md](capabilities.md); lifecycle hooks in [visits-lifecycle.md](visits-lifecycle.md).

---

## Output accountability

`produces` is an enforceable contract, not descriptive metadata.

### Artifact declarations

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

### Publishing artifacts

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

### Concrete artifact references

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

### Consuming artifacts

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

### Receipts are evidence

Receipts are engine-recorded evidence about how work was performed. They are not artifacts unless a downstream node consumes the receipt itself as a declared domain output.

For example, build receipts should normally be produced by the worker-completion or transition CLI operation. The worker contract and instructions define the completion payload; the CLI combines that payload with engine-owned provenance, validates the result against a schema listed under `receipts`, stores it under the run's receipt area, and appends `receipt.linked`. The builder does not invent the receipt id or durable filename. An `on_seal` check can require the expected receipt evidence without declaring `build-receipts` as a work artifact.

For a gate, the accountable output is `visit.decision`. The engine MUST reject a normal close request or completed seal unless the decision is one of `produces.options`.

The workflow is a control-flow graph, not a typed dataflow graph. A connection establishes execution order but does not bind one node's artifact to another node's input. `reads` declares accessible context; it does not prove that data exists or came from the current cycle. A node that depends on prior data MUST verify its readiness and provenance with an `on_examine` or `on_open` check.
