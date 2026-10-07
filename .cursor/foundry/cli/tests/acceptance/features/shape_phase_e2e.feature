@foundry.shape.e2e
Feature: shape phase end-to-end
  As a shape steward
  I want the full shape phase to advance from run create through execute.start
  So that intake, examination, presentation, recording, and gates compose correctly

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Full shape phase from run create through execute.start
    When I invoke "run create"
    Then the CLI succeeds
    And I store run id from response field "run_id"
    When I invoke "visit state patch" with set '{"app_folder": "."}'
    Then the CLI succeeds
    When I invoke visit intake complete with work prompt "E2E shape phase work request"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.examine |
    When I prepare shape examine agent wait without auto submit
    When I submit examination result with no open questions
    Then the CLI succeeds
    When I invoke visit examine complete
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.present |
    When I prepare shape present agent wait without auto submit
    And I submit presentation result with PROCEED verdict
    When I invoke "visit present complete"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.present.gate |
    When I invoke "gate decide" with decision "accept"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.record |
    When I prepare shape record agent wait without auto submit
    And I submit record result with PROCEED verdict
    When I invoke "visit record complete"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.record.gate |
    When I invoke "gate decide" with decision "accept"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | execute.start |
      | next_lifecycle | opened |
