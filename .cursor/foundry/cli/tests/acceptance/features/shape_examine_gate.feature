@node.shape.examine.gate
Feature: shape.examine.gate vertical slice
  As a shape steward
  I want gate decide for shape.examine.gate
  So that I can route to present or continue questioning

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Decide accept routes to shape.present
    Given run fixture "porcelain-0007-v003-examine-gate" in temporary workspace
    When I invoke "gate decide" with json output and decision "accept"
    Then the CLI exit code is 0
    And response ok is true
    And response field "next_node_id" equals "shape.present"
    And response field "next_lifecycle" equals "opened"
    And response field "decision" equals "accept"

  Scenario: Decide reject routes to shape.examine
    Given run fixture "porcelain-0007-v003-examine-gate" in temporary workspace
    When I invoke "gate decide" with json output and decision "reject"
    Then the CLI exit code is 0
    And response ok is true
    And response field "next_node_id" equals "shape.examine"
    And response field "next_lifecycle" equals "opened"
    And response field "decision" equals "reject"

  Scenario: Invalid decision is rejected
    Given run fixture "porcelain-0007-v003-examine-gate" in temporary workspace
    When I invoke "gate decide" with json output and decision "present"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "INVALID_GATE_DECISION"

  Scenario: Visit transition on gate is rejected
    Given run fixture "porcelain-0007-v003-examine-gate" in temporary workspace
    When I invoke "visit transition" with json output and summary "Should not work"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "GATE_USE_DECIDE"

  Scenario: on_examine failure halts run without prior examine sealed
    Given run fixture "porcelain-0007-v003-examine-gate-examined"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field     | expected           |
      | node_id   | shape.examine.gate |
      | lifecycle | examined           |
    And the run snapshot status is "halted"

  Scenario: Run context for shape.examine.gate opened visit
    Given run fixture "porcelain-0007-v003-examine-gate"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field             | expected                                              |
      | node_id           | shape.examine.gate                                    |
      | visit_id          | v-003                                                 |
      | kind              | gate                                                  |
      | lifecycle         | opened                                                |
      | instructions      | registry:nodes/shape.examine.gate/instructions.md     |
      | instructions_path | (file exists)                                         |
      | prompt            | Examination still has open clarifying questions. Reject to continue questioning, or accept to proceed to present the plan with the remaining assumptions visible. |
    And context allow cli equals:
      | capability |
    And context produces options equal:
      | option |
      | accept |
      | reject |
    And context allow user decide is true
