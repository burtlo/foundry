Feature: Persistent local job host
  As an operator
  I want a workspace-local host to own durable run advancement
  So that runs outlive short-lived CLI processes

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Local run advance reaches present gate after shape path
    When I invoke "run create" with work prompt "Advance contract proof"
    Then the CLI succeeds
    And I store run id from response field "run_id"
    When I invoke "run advance" with flag "--local"
    Then the CLI succeeds with:
      | field | expected |
      | active_node_id | shape.present.gate |
    When I invoke "run get" with flag "--local"
    Then the CLI succeeds with:
      | field | expected |
      | wait.kind | decision |

  Scenario: Foreground host serves run get after create and advance
    Given the foreground job host is running for the workspace
    When I invoke "host status"
    Then the CLI succeeds with:
      | field | expected |
      | running | True |
    When I invoke "run create" with work prompt "Host integration proof"
    Then the CLI succeeds
    And I store run id from response field "run_id"
    When I invoke "run advance"
    Then the CLI succeeds
    When I invoke "run get"
    Then the CLI succeeds with:
      | field | expected |
      | active_node_id | shape.present.gate |
      | wait.kind | decision |
