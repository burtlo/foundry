@node.shape.record.gate
Feature: shape.record.gate vertical slice
  As a shape steward
  I want gate decide for shape.record.gate
  So that I can confirm acceptance criteria and route to execute.start

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Decide accept routes to execute.start
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I invoke "gate decide" with decision "accept"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | execute.start |
      | next_lifecycle | opened |
      | decision | accept |

  Scenario: Decide hold routes to shape.present for refinement
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I invoke "gate decide" with decision "hold"
    Then the CLI succeeds with:
      | field | expected |
      | decision | hold |
      | lifecycle | sealed |
      | next_node_id | shape.present |
      | next_lifecycle | opened |

  Scenario: Hold then run advance keeps run runnable on shape.present
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I invoke "gate decide" with decision "hold"
    Then the CLI succeeds
    When I invoke "run advance"
    Then the CLI succeeds
    And the run snapshot status is "running"

  Scenario: Invalid decision is rejected
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I invoke "gate decide" with decision "record"
    Then the CLI fails with error "INVALID_GATE_DECISION"

  Scenario: Visit transition on gate is rejected
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I invoke "visit transition" with summary "Should not work"
    Then the CLI fails with error "GATE_USE_DECIDE"

  Scenario: on_examine failure halts run without prior record sealed or approved_ac
    Given run fixture "porcelain-0007-v007-record-gate-examined"
    When I invoke "run context"
    Then the CLI succeeds
    And context fields match:
      | field     | expected          |
      | node_id   | shape.record.gate |
      | lifecycle | examined          |
    And the run snapshot status is "halted"

  Scenario: Run context for shape.record.gate opened visit
    Given run fixture "porcelain-0007-v007-record-gate"
    When I invoke "run context"
    Then the CLI succeeds
    And context fields match:
      | field             | expected                                                                                                              |
      | node_id           | shape.record.gate                                                                                                     |
      | visit_id          | v-007                                                                                                                 |
      | kind              | gate                                                                                                                  |
      | lifecycle         | opened                                                                                                                |
      | instructions      | registry:nodes/shape.record.gate/instructions.md                                                                      |
      | instructions_path | (file exists)                                                                                                         |
      | prompt            | Living plan and approved_ac are frozen. The user accepts shared understanding of acceptance criteria before execute may start, or holds to request changes. |
      | reads.artifacts[0].artifact | shape.record.plan                                                                                           |
      | reads.artifacts[0].from       | nearest_sealed_ancestor                                                                                       |
    And context allow cli equals:
      | capability |
    And context produces options equal:
      | option |
      | accept |
      | hold   |
    And context allow user decide is true
