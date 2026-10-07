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
    When I invoke "gate decide" with decision "reject"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.examine |
      | next_lifecycle | opened |
      | decision | reject |

  Scenario: Decide accept routes to shape.record
    Given run fixture "porcelain-0007-v005-present-gate" in temporary workspace
    When I invoke "gate decide" with decision "accept"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.record |
      | next_lifecycle | opened |
      | decision | accept |

  Scenario: Invalid decision is rejected
    Given run fixture "porcelain-0007-v005-present-gate" in temporary workspace
    When I invoke "gate decide" with decision "refine"
    Then the CLI fails with error "INVALID_GATE_DECISION"

  Scenario: Visit transition on gate is rejected
    Given run fixture "porcelain-0007-v005-present-gate" in temporary workspace
    When I invoke "visit transition" with summary "Should not work"
    Then the CLI fails with error "GATE_USE_DECIDE"

  Scenario: on_examine failure halts run without prior present sealed
    Given run fixture "porcelain-0007-v005-present-gate-presented"
    When I invoke "run context"
    Then the CLI succeeds
    And context fields match:
      | field     | expected           |
      | node_id   | shape.present.gate |
      | lifecycle | examined           |
    And the run snapshot status is "halted"

  Scenario: Run context for shape.present.gate opened visit
    Given run fixture "porcelain-0007-v005-present-gate"
    When I invoke "run context"
    Then the CLI succeeds
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
