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
    When I invoke "gate decide" with decision "accept"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.present |
      | next_lifecycle | opened |
      | decision | accept |

  Scenario: Decide reject routes to shape.examine
    Given run fixture "porcelain-0007-v003-examine-gate" in temporary workspace
    When I invoke "gate decide" with decision "reject"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.examine |
      | next_lifecycle | opened |
      | decision | reject |

  Scenario: Invalid decision is rejected
    Given run fixture "porcelain-0007-v003-examine-gate" in temporary workspace
    When I invoke "gate decide" with decision "present"
    Then the CLI fails with error "INVALID_GATE_DECISION"

  Scenario: Visit transition on gate is rejected
    Given run fixture "porcelain-0007-v003-examine-gate" in temporary workspace
    When I invoke "visit transition" with summary "Should not work"
    Then the CLI fails with error "GATE_USE_DECIDE"

  Scenario: on_examine failure halts run without prior examine sealed
    Given run fixture "porcelain-0007-v003-examine-gate-examined"
    When I invoke "run context"
    Then the CLI succeeds
    And context fields match:
      | field     | expected           |
      | node_id   | shape.examine.gate |
      | lifecycle | examined           |
    And the run snapshot status is "halted"

  Scenario: Run context for shape.examine.gate opened visit
    Given run fixture "porcelain-0007-v003-examine-gate"
    When I invoke "run context"
    Then the CLI succeeds
    And context fields match:
      | field                                  | expected                                                                                                              |
      | node_id                                | shape.examine.gate                                                                                                    |
      | visit_id                               | v-003                                                                                                                 |
      | kind                                   | gate                                                                                                                  |
      | lifecycle                              | opened                                                                                                                |
      | title                                  | Open questions remain — present anyway or continue examination                                                        |
      | instructions                           | registry:nodes/shape.examine.gate/instructions.md                                                                     |
      | instructions_path                      | (file exists)                                                                                                         |
      | prompt                                 | Examination still has open clarifying questions. Reject to continue questioning, or accept to proceed to present the plan with the remaining assumptions visible. |
      | reads.state.draft_ac                   | Partial AC.                                                                                                           |
      | reads.state.open_clarifying_questions_count | 1                                                                                                                |
      | reads.state.clarifying_questions       | None                                                                                                                  |
      | reads.state.assumptions                | None                                                                                                                  |
      | reads.state.examination_decisions      | None                                                                                                                  |
    And context allow cli equals:
      | capability |
    And context produces options equal:
      | option |
      | accept |
      | reject |
    And context allow user decide is true
