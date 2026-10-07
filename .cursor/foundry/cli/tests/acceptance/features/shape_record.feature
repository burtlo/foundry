@node.shape.record
Feature: shape.record vertical slice
  As a shape steward
  I want record judgment and engine completion
  So that I can reach shape.record.gate without manual receipt orchestration

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Happy path routes to shape.record.gate
    Given run fixture "porcelain-0007-v006-record" in temporary workspace
    When I prepare shape record agent wait without auto submit
    And I submit record result with PROCEED verdict
    When I invoke "visit record complete"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.record.gate |
      | next_lifecycle | opened |

  Scenario: Blocked path seals agent receipt without publish or transition
    Given run fixture "porcelain-0007-v006-record" in temporary workspace
    When I prepare shape record agent wait without auto submit
    And I submit record result with BLOCKED verdict
    When I invoke "run context"
    Then the CLI succeeds
    And context fields match:
      | field     | expected     |
      | node_id   | shape.record |
      | lifecycle | opened       |

  Scenario: Complete without PROCEED judgment fails
    Given run fixture "porcelain-0007-v006-record" in temporary workspace
    When I prepare shape record agent wait without auto submit
    And I submit record result with BLOCKED verdict
    When I invoke "visit record complete"
    Then the CLI fails with error "RECORD_BLOCKED"

  Scenario: Complete without judgment fails
    Given run fixture "porcelain-0007-v006-record" in temporary workspace
    When I invoke "visit record complete"
    Then the CLI fails with error "JUDGMENT_MISSING"

  Scenario: on_examine failure halts run without prior present sealed
    Given run fixture "porcelain-0007-v006-record-examined"
    When I invoke "run context"
    Then the CLI succeeds
    And context fields match:
      | field     | expected     |
      | node_id   | shape.record |
      | lifecycle | examined     |
    And the run snapshot status is "halted"

  Scenario: Gate decide on step is capability denied
    Given run fixture "porcelain-0007-v006-record" in temporary workspace
    When I invoke "gate decide" with decision "accept"
    Then the CLI fails with error "CAPABILITY_DENIED"

  Scenario: Artifact publish denied on opened record visit
    Given run fixture "porcelain-0007-v006-record" in temporary workspace
    When I invoke "artifact publish" with artifact "plan" from "run:artifacts/v-006/plan.md"
    Then the CLI fails with error "CAPABILITY_DENIED"

  Scenario: Run context for shape.record opened visit
    Given run fixture "porcelain-0007-v006-record"
    When I invoke "run context"
    Then the CLI succeeds
    And context fields match:
      | field                              | expected                                   |
      | node_id                            | shape.record                               |
      | visit_id                           | v-006                                      |
      | lifecycle                          | opened                                     |
      | instructions                       | registry:nodes/shape.record/judgment.md    |
      | instructions_path                  | (file exists)                              |
    And context allow cli equals:
      | capability            |
      | run.agent.submit      |
      | visit.record.complete |
