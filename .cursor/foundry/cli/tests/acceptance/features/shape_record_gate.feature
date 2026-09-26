@node.shape.record.gate
Feature: shape.record.gate vertical slice
  As a shape steward
  I want gate decide for shape.record.gate
  So that I can confirm acceptance criteria and route to execute.start

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Decide record routes to execute.start
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I invoke "gate decide" with json output and decision "record"
    Then the CLI exit code is 0
    And response ok is true
    And response field "next_node_id" equals "execute.start"
    And response field "next_lifecycle" equals "opened"
    And response field "decision" equals "record"

  Scenario: Invalid decision is rejected
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I invoke "gate decide" with json output and decision "refine"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "INVALID_GATE_DECISION"

  Scenario: Visit transition on gate is rejected
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I invoke "visit transition" with json output and summary "Should not work"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "GATE_USE_DECIDE"

  Scenario: on_examine failure halts run without prior record sealed or approved_ac
    Given run fixture "porcelain-0007-v007-record-gate-examined"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field     | expected          |
      | node_id   | shape.record.gate |
      | lifecycle | examined          |
    And the run snapshot status is "halted"

  Scenario: Run context for shape.record.gate opened visit
    Given run fixture "porcelain-0007-v007-record-gate"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field             | expected                                                                                                              |
      | node_id           | shape.record.gate                                                                                                     |
      | visit_id          | v-007                                                                                                                 |
      | kind              | gate                                                                                                                  |
      | lifecycle         | opened                                                                                                                |
      | instructions      | registry:nodes/shape.record.gate/instructions.md                                                                      |
      | instructions_path | (file exists)                                                                                                         |
      | prompt            | Record the living plan and approved_ac. The user confirms shared understanding of acceptance criteria before execute may start. |
    And context allow cli equals:
      | capability |
    And context produces options equal:
      | option |
      | record |
    And context allow user decide is true
