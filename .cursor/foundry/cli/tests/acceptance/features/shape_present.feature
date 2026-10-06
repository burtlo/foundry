@node.shape.present
Feature: shape.present vertical slice
  As a shape steward
  I want presentation judgment and engine completion
  So that I can reach shape.present.gate without manual receipt orchestration

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Happy path routes to shape.present.gate
    Given run fixture "porcelain-0007-v004-present" in temporary workspace
    When I prepare shape present agent wait without auto submit
    And I submit presentation result with PROCEED verdict
    When I invoke "visit present complete" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "next_node_id" equals "shape.present.gate"
    And response field "next_lifecycle" equals "opened"

  Scenario: Blocked path seals agent receipt without publish or transition
    Given run fixture "porcelain-0007-v004-present" in temporary workspace
    When I prepare shape present agent wait without auto submit
    And I submit presentation result with BLOCKED verdict
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field     | expected      |
      | node_id   | shape.present |
      | lifecycle | opened        |

  Scenario: Complete without PROCEED judgment fails
    Given run fixture "porcelain-0007-v004-present" in temporary workspace
    When I prepare shape present agent wait without auto submit
    And I submit presentation result with BLOCKED verdict
    When I invoke "visit present complete" with json output
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "PRESENTATION_BLOCKED"

  Scenario: Complete without judgment fails
    Given run fixture "porcelain-0007-v004-present" in temporary workspace
    When I invoke "visit present complete" with json output
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "JUDGMENT_MISSING"

  Scenario: on_examine failure halts run without prior examine sealed
    Given run fixture "porcelain-0007-v004-present-examined"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field     | expected      |
      | node_id   | shape.present |
      | lifecycle | examined      |
    And the run snapshot status is "halted"

  Scenario: Gate decide on step is capability denied
    Given run fixture "porcelain-0007-v004-present" in temporary workspace
    When I invoke "gate decide" with json output and decision "reject"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CAPABILITY_DENIED"

  Scenario: Artifact publish denied on opened present visit
    Given run fixture "porcelain-0007-v004-present" in temporary workspace
    When I invoke "artifact publish" with json output and artifact "presentation" from "run:artifacts/v-004/presentation.md"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CAPABILITY_DENIED"

  Scenario: Mutating command rejected when lifecycle examined
    Given run fixture "porcelain-0007-v004-present-examined"
    When I invoke "visit state patch" with json output and set '{"presented_ac": "blocked"}'
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CAPABILITY_DENIED"

  Scenario: Run context for shape.present opened visit
    Given run fixture "porcelain-0007-v004-present"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field                              | expected                                     |
      | node_id                            | shape.present                                |
      | visit_id                           | v-004                                        |
      | lifecycle                          | opened                                       |
      | instructions                       | registry:nodes/shape.present/judgment.md       |
      | instructions_path                  | (file exists)                                |
    And context allow cli equals:
      | capability           |
      | run.agent.submit     |
      | visit.present.complete |
