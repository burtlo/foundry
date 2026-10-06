@node.shape.present.gate
Feature: shape.present.gate vertical slice
  As a shape steward
  I want gate decide for shape.present.gate
  So that I can route to refine examination or record acceptance criteria

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Decide reject routes to shape.examine
    Given run fixture "porcelain-0007-v005-present-gate" in temporary workspace
    When I invoke "gate decide" with json output and decision "reject"
    Then the CLI exit code is 0
    And response ok is true
    And response field "next_node_id" equals "shape.examine"
    And response field "next_lifecycle" equals "opened"
    And response field "decision" equals "reject"

  Scenario: Decide accept routes to shape.record
    Given run fixture "porcelain-0007-v005-present-gate" in temporary workspace
    When I invoke "gate decide" with json output and decision "accept"
    Then the CLI exit code is 0
    And response ok is true
    And response field "next_node_id" equals "shape.record"
    And response field "next_lifecycle" equals "opened"
    And response field "decision" equals "accept"

  Scenario: Invalid decision is rejected
    Given run fixture "porcelain-0007-v005-present-gate" in temporary workspace
    When I invoke "gate decide" with json output and decision "refine"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "INVALID_GATE_DECISION"

  Scenario: Visit transition on gate is rejected
    Given run fixture "porcelain-0007-v005-present-gate" in temporary workspace
    When I invoke "visit transition" with json output and summary "Should not work"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "GATE_USE_DECIDE"

  Scenario: on_examine failure halts run without prior present sealed
    Given run fixture "porcelain-0007-v005-present-gate-presented"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field     | expected           |
      | node_id   | shape.present.gate |
      | lifecycle | examined           |
    And the run snapshot status is "halted"

  Scenario: Run context for shape.present.gate opened visit
    Given run fixture "porcelain-0007-v005-present-gate"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field             | expected                                                                                    |
      | node_id           | shape.present.gate                                                                          |
      | visit_id          | v-005                                                                                       |
      | kind              | gate                                                                                        |
      | lifecycle         | opened                                                                                      |
      | instructions      | registry:nodes/shape.present.gate/instructions.md                                           |
      | instructions_path | (file exists)                                                                               |
      | prompt            | Succinct plan presentation shown. Reject to return to examination, or accept to record acceptance criteria. |
      | reads.artifacts[0].artifact | shape.present.presentation                                                          |
      | reads.artifacts[0].from       | nearest_sealed_ancestor                                                             |
      | reads.artifacts[0].resolved_uri | run:artifacts/v-004/presentation.md                                                 |
    And context allow cli equals:
      | capability |
    And context produces options equal:
      | option |
      | reject |
      | accept |
    And context allow user decide is true
