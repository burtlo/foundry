@node.shape.intake
Feature: foundry run context
  As a phase steward
  I want the engine to assemble a context packet for my active visit
  So that I can execute step instructions without re-reading factory-flow.yaml

  Read-only: this command must not append ledger events.

  Background:
    Given the foundry registry flow "implementation"
    And workspace is the repository root

  Scenario: Steward loads context before shape.intake work
    Given run fixture "porcelain-0007-v001"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context validates against schema "context-packet.schema.json"
    And context fields match:
      | field                              | expected                            |
      | node_id                            | shape.intake                        |
      | visit_id                           | v-001                               |
      | lifecycle                          | opened                              |
      | run_id                             | porcelain-0007                      |
      | instructions                       | registry:nodes/shape.intake/instructions.md |
      | instructions_path                  | (file exists)                       |
      | worker.mode                        | shape                               |
      | produces.artifacts[0].id           | ticket                              |
      | produces.artifacts[0].resolved_uri   | run:artifacts/v-001/ticket.json     |
    And context allow cli equals:
      | capability        |
      | artifact.publish  |
      | ledger.show       |
      | receipt.link      |
      | transition        |
      | visit.state_patch |
    And context allow files write uris include:
      | uri                              |
      | run:ticket.json                  |
      | run:artifacts/v-001/ticket.json |
      | run:receipts/intake.json         |
      | run:receipts/agent.json          |
    And context allow state includes "state.nodes.shape.intake.*"
    And no ledger events are appended

  Scenario: Steward loads markdown context packet
    Given run fixture "porcelain-0007-v001"
    When I invoke "run context" with markdown output
    Then the CLI exit code is 0
    And markdown output contains "## Instructions"
    And markdown output contains "# Shape intake"
    And markdown output contains "artifact.publish"

  Scenario: Steward loads markdown context for shape.examine
    Given run fixture "porcelain-0007-v002-examine"
    When I invoke "run context" with markdown output
    Then the CLI exit code is 0
    And markdown output contains "# Shape examination"
    And markdown output contains "visit state patch"

  Scenario: Steward loads markdown context for shape.examine.gate
    Given run fixture "porcelain-0007-v003-examine-gate"
    When I invoke "run context" with markdown output
    Then the CLI exit code is 0
    And markdown output contains "# Examination gate"
    And markdown output contains "gate decide"

  Scenario: Steward loads markdown context for shape.present
    Given run fixture "porcelain-0007-v004-present"
    When I invoke "run context" with markdown output
    Then the CLI exit code is 0
    And markdown output contains "# Shape presentation"
    And markdown output contains "shape-presenter"
    And markdown output contains "artifact.publish"

  Scenario: Steward loads markdown context for shape.present.gate
    Given run fixture "porcelain-0007-v005-present-gate"
    When I invoke "run context" with markdown output
    Then the CLI exit code is 0
    And markdown output contains "# Plan presentation gate"
    And markdown output contains "Turn 1 — Presentation"
    And markdown output contains "presented_ac"
    And markdown output contains "shape.present.presentation"
    And markdown output contains "gate decide"

  Scenario: Steward loads markdown context for shape.record
    Given run fixture "porcelain-0007-v006-record"
    When I invoke "run context" with markdown output
    Then the CLI exit code is 0
    And markdown output contains "# Shape record"
    And markdown output contains "shape-recorder"
    And markdown output contains "artifact publish"
    And markdown output contains "visit state patch"

  Scenario: Steward loads markdown context for shape.record.gate
    Given run fixture "porcelain-0007-v007-record-gate"
    When I invoke "run context" with markdown output
    Then the CLI exit code is 0
    And markdown output contains "# Record acceptance criteria gate"
    And markdown output contains "Turn 1 — Presentation"
    And markdown output contains "approved_ac"
    And markdown output contains "shape.record.plan"
    And markdown output contains "gate decide"

  Scenario: Json and markdown flags are mutually exclusive
    Given run fixture "porcelain-0007-v001"
    When I invoke "run context" with json output and flag "--markdown"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "INVALID_FLAGS"

  Scenario: Missing run directory
    When I invoke "run context" with run id "does-not-exist" and json output
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "RUN_NOT_FOUND"

  Scenario: Visit not opened returns context with warning
    Given run fixture "porcelain-0007-v001-examined"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field     | expected  |
      | lifecycle | examined  |
    And context warnings mention lifecycle "opened"
