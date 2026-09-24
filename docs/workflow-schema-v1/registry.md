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
        prompt: registry:agents/intake-checker.shape.md
        contract: registry:contracts/intake-checker.shape.yaml
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
