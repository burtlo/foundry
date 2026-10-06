# Registry document

This document shows one full conforming registry document. It composes patterns from [graph.md](graph.md), [capabilities.md](capabilities.md), [visits-lifecycle.md](visits-lifecycle.md), [artifacts.md](artifacts.md), and [control-plane.md](control-plane.md). For validation rules, see [validation.md](validation.md).

---

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
      title: Shape intake — validate app manifest and capture work request
      produces:
        artifacts:
          - id: ticket
            kind: document
            uri: "run:artifacts/{visit_id}/ticket.json"
            schema: registry:schemas/ticket.schema.json
            media_type: application/json
      reads:
        config: [workspace]
        state: [app_folder]
      allow:
        state: [app_folder]
        cli: [visit.intake.complete, visit.state_patch]
      lifecycle:
        on_open:
          - check: validate-manifest
        on_seal:
          - check: intake-receipt-sealed
          - check: agent-receipt-sealed
      receipts:
        - registry:schemas/intake-receipt.schema.json
        - registry:schemas/agent-receipt.schema.json

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
        decisions: [accept]

    - id: review-needs-changes
      from: acceptance-review
      to: shape.intake
      on:
        outcomes: [completed]
        decisions: [needs_changes]
```

Authored YAML SHOULD omit empty fields and values equal to documented defaults.
