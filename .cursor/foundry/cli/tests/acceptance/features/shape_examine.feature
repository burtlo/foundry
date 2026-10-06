@node.shape.examine
Feature: shape.examine vertical slice
  As a shape steward
  I want mutating CLI commands for shape.examine
  So that I can conduct examination, seal agent receipt, and route to present or gate

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Fast lane happy path routes to shape.present
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I invoke "visit state patch" with json output and set '{"draft_ac": "User can log in.", "open_clarifying_questions_count": 0}'
    Then the CLI exit code is 0
    And response ok is true
    And I write examine agent receipt draft to the run directory
    When I invoke "ledger show" with json output and types "check.recorded"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "visit transition" with json output and summary "Shape examination complete"
    Then the CLI exit code is 0
    And response ok is true
    And response field "next_node_id" equals "shape.present"
    And response field "next_lifecycle" equals "opened"

  Scenario: Gate path routes to shape.examine.gate when open questions remain
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I invoke "visit state patch" with json output and set '{"draft_ac": "Partial AC.", "open_clarifying_questions_count": 1}'
    Then the CLI exit code is 0
    And I write examine agent receipt draft to the run directory
    When I invoke "ledger show" with json output and types "check.recorded"
    Then the CLI exit code is 0
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    When I invoke "visit transition" with json output and summary "Shape examination complete"
    Then the CLI exit code is 0
    And response ok is true
    And response field "next_node_id" equals "shape.examine.gate"
    And response field "next_lifecycle" equals "opened"

  Scenario: Transition without agent receipt reopens visit
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I invoke "visit state patch" with json output and set '{"open_clarifying_questions_count": 0}'
    Then the CLI exit code is 0
    When I invoke "visit transition" with json output and summary "Missing agent receipt"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CHECK_FAILED"

  Scenario: on_examine failure halts run at examined lifecycle
    Given run fixture "porcelain-0007-v002-examine-examined"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field     | expected      |
      | node_id   | shape.examine |
      | lifecycle | examined      |
    And the run snapshot status is "halted"

  Scenario: Visit state patch denied for disallowed key
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I invoke "visit state patch" with json output and set '{"ticket": "override"}'
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "STATE_PATCH_DENIED"

  Scenario: Mutating command rejected when lifecycle examined
    Given run fixture "porcelain-0007-v002-examine-examined"
    When I invoke "visit state patch" with json output and set '{"draft_ac": "blocked"}'
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "VISIT_NOT_OPENED"

  Scenario: Run context for shape.examine opened visit
    Given run fixture "porcelain-0007-v002-examine"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field                              | expected                                         |
      | node_id                            | shape.examine                                    |
      | visit_id                           | v-002                                            |
      | lifecycle                          | opened                                           |
      | instructions                       | registry:nodes/shape.examine/judgment.md     |
      | operations                         | registry:nodes/shape.examine/operations.yaml |
      | instructions_path                  | (file exists)                                    |
      | reads.artifacts[0].artifact        | shape.intake.ticket                              |
      | reads.artifacts[0].from            | nearest_sealed_ancestor                          |
    And context allow cli equals:
      | capability        |
      | ledger.show       |
      | receipt.link      |
      | transition        |
      | visit.state_patch |
    And context allow files write uris include:
      | uri                    |
      | run:receipts/agent.json |
    And context allow state includes "state.nodes.shape.examine.*"
    And context allow user ask is true

  Scenario: End-to-end from run create through examine transition
    When I invoke "run create" with json output
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    When I invoke "visit state patch" with json output and set '{"app_folder": "."}'
    Then the CLI exit code is 0
    And I write ticket draft to the run directory
    And I write receipt drafts to the run directory
    When I invoke "artifact publish" with json output and artifact "ticket" from "run:ticket.json"
    Then the CLI exit code is 0
    When I invoke "ledger show" with json output and types "check.recorded"
    Then the CLI exit code is 0
    When I invoke "receipt seal" with json output schema "registry:schemas/intake-receipt.schema.json" file "run:receipts/intake.json"
    Then the CLI exit code is 0
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    When I invoke "visit transition" with json output and summary "Shape intake complete"
    Then the CLI exit code is 0
    And response field "next_node_id" equals "shape.examine"
    When I invoke "visit state patch" with json output and set '{"draft_ac": "E2E AC.", "open_clarifying_questions_count": 0}'
    Then the CLI exit code is 0
    And I write examine agent receipt draft to the run directory
    When I invoke "ledger show" with json output and types "check.recorded"
    Then the CLI exit code is 0
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    When I invoke "visit transition" with json output and summary "Shape examination complete"
    Then the CLI exit code is 0
    And response field "next_node_id" equals "shape.present"
