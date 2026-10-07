@node.execute.plan
Feature: execute.plan vertical slice
  As an execute steward
  I want plan judgment and engine completion
  So that I can reach execute.build without manual publish orchestration

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest
    And execute workspace has app manifest and clean git

  Scenario: Happy path routes to execute.build
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I prepare execute plan agent wait without auto submit
    And I submit plan result with PROCEED verdict
    When I invoke "visit plan complete"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | execute.build |
      | next_lifecycle | opened |

  Scenario: Complete without PROCEED judgment fails
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I prepare execute plan agent wait without auto submit
    And I submit plan result with BLOCKED verdict
    When I invoke "visit plan complete"
    Then the CLI fails with error "PLAN_BLOCKED"

  Scenario: Complete without judgment fails
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I prepare execute plan opened visit at execute.plan
    When I invoke "visit plan complete"
    Then the CLI fails with error "JUDGMENT_MISSING"

  Scenario: Run context for execute.plan opened visit
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I prepare execute plan opened visit at execute.plan
    When I invoke "run context"
    Then the CLI succeeds
    And context fields match:
      | field             | expected                                  |
      | node_id           | execute.plan                              |
      | lifecycle         | opened                                    |
      | instructions      | registry:nodes/execute.plan/judgment.md   |
      | instructions_path | (file exists)                             |
    And context allow cli equals:
      | capability          |
      | run.agent.submit    |
      | visit.plan.complete |
