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
    When I invoke "shape" with json output and input "Add rate limiting to the API" and flag "--no-host"
    Then the CLI exit code is 0
    And response ok is true
    And I store run id from response field "run_id"
    And response field "active_node_id" equals "shape.present.gate"
    And response field "wait.kind" equals "decision"
    And response field "work_prompt" equals "Add rate limiting to the API"
    When I invoke "runs" with json output and flag "--local"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "status" with json output and flag "--local"
    Then the CLI exit code is 0
    And response ok is true
    And response field "run_id" equals "stored run id"
    When I invoke "attach" with json output and flags "--no-follow --local"
    Then the CLI exit code is 0
    And response ok is true
    And response field "run_id" equals "stored run id"

  Scenario: Answer while at a user gate returns WAIT_KIND_MISMATCH
    When I invoke "shape" with json output and input "Need gate decisions" and flag "--no-host"
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    And response field "wait.kind" equals "decision"
    When I invoke "answer" with json output and answers '{"q1": "n/a"}' and flag "--local"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "WAIT_KIND_MISMATCH"

  Scenario: Start authorizes execute at execute.start
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I invoke "gate decide" with json output and decision "accept"
    Then the CLI exit code is 0
    When I invoke "run advance" with json output
    Then the CLI exit code is 0
    And response field "active_node_id" equals "execute.start"
    And response field "wait.kind" equals "decision"
    When I invoke "start" with json output and flags "--no-host --local"
    Then the CLI exit code is 0
    And response ok is true
    And response field "authorization_recorded" equals "True"
    And response field "active_node_id" equals "execute.intake"
    And response field "phase" equals "execute"

  Scenario: Cancel requires a reason
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    When I invoke "cancel" with json output
    Then the CLI exit code is 2
