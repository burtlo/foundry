Feature: Persistent local job host
  As an operator
  I want a workspace-local host to own durable run advancement
  So that runs outlive short-lived CLI processes

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Local run advance reaches shape.examine after intake
    When I invoke "run create" with json output and work prompt "Advance contract proof"
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    When I invoke "run advance" with json output and flag "--local"
    Then the CLI exit code is 0
    And response ok is true
    And response field "active_node_id" equals "shape.examine"
    When I invoke "run get" with json output and flag "--local"
    Then the CLI exit code is 0
    And response field "wait.kind" equals "operator"

  Scenario: Foreground host serves run get after create and advance
    Given the foreground job host is running for the workspace
    When I invoke "host status" with json output
    Then the CLI exit code is 0
    And response field "running" equals "True"
    When I invoke "run create" with json output and work prompt "Host integration proof"
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    When I invoke "run advance" with json output
    Then the CLI exit code is 0
    When I invoke "run get" with json output
    Then the CLI exit code is 0
    And response field "active_node_id" equals "shape.examine"
    And response field "wait.kind" equals "operator"
