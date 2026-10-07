@cli.user
Feature: User CLI for Shape and supervision
  As a developer shaping work in Foundry
  I want high-level foundry commands for Shape and gates
  So that I do not orchestrate low-level visit commands by hand

  Foundry controls workflow execution; these commands submit inputs and read snapshots.
  The job host (when running) performs durable advancement — agents perform judgment only.

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Shape creates a run and persists the work prompt without the host
    When I invoke "shape" with input "Add rate limiting to the API" and flag "--no-host"
    Then the CLI succeeds
    And I store run id from response field "run_id"
    And response field "active_node_id" equals "shape.present.gate"
    And response field "wait.kind" equals "decision"
    And response field "work_prompt" equals "Add rate limiting to the API"
    When I invoke "runs" with flag "--local"
    Then the CLI succeeds
    When I invoke "status" with flag "--local"
    Then the CLI succeeds
    And response field "run_id" equals "stored run id"
    When I invoke "attach" with flags "--no-follow --local"
    Then the CLI succeeds
    And response field "run_id" equals "stored run id"

  Scenario: Answer while at a user gate returns WAIT_KIND_MISMATCH
    When I invoke "shape" with input "Need gate decisions" and flag "--no-host"
    Then the CLI succeeds
    And I store run id from response field "run_id"
    And response field "wait.kind" equals "decision"
    When I invoke "answer" with answers '{"q1": "n/a"}' and flag "--local"
    Then the CLI fails with error "WAIT_KIND_MISMATCH"

  Scenario: Start authorizes execute at execute.start
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I invoke "gate decide" with decision "accept"
    Then the CLI succeeds
    When I invoke "run advance"
    Then the CLI succeeds with:
      | field | expected |
      | active_node_id | execute.start |
      | wait.kind | decision |
    When I invoke "start" with flags "--no-host --local"
    Then the CLI succeeds with:
      | field | expected |
      | authorization_recorded | True |
      | active_node_id | execute.intake |
      | phase | execute |

  Scenario: Cancel requires a reason
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I invoke "cancel"
    Then the CLI exit code is 2
