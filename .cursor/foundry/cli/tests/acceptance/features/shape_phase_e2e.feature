@node.shape.intake
Feature: shape phase end-to-end
  As a shape steward
  I want the full shape phase to advance from run create through execute.start
  So that intake, examination, presentation, recording, and gates compose correctly

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Full shape phase from run create through execute.start
    When I invoke "run create" with json output
    Then the CLI exit code is 0
    And response ok is true
    And I store run id from response field "run_id"
    When I invoke "visit state patch" with json output and set '{"app_folder": "."}'
    Then the CLI exit code is 0
    When I invoke visit intake complete with work prompt "E2E shape phase work request"
    Then the CLI exit code is 0
    And response field "next_node_id" equals "shape.examine"
    When I prepare shape examine agent wait without auto submit
    When I submit examination result with no open questions
    Then the CLI exit code is 0
    When I invoke visit examine complete with json output
    Then the CLI exit code is 0
    And response field "next_node_id" equals "shape.present"
    When I prepare shape present agent wait without auto submit
    And I submit presentation result with PROCEED verdict
    When I invoke "visit present complete" with json output
    Then the CLI exit code is 0
    And response field "next_node_id" equals "shape.present.gate"
    When I invoke "gate decide" with json output and decision "accept"
    Then the CLI exit code is 0
    And response field "next_node_id" equals "shape.record"
    When I prepare shape record agent wait without auto submit
    And I submit record result with PROCEED verdict
    When I invoke "visit record complete" with json output
    Then the CLI exit code is 0
    And response field "next_node_id" equals "shape.record.gate"
    When I invoke "gate decide" with json output and decision "accept"
    Then the CLI exit code is 0
    And response field "next_node_id" equals "execute.start"
    And response field "next_lifecycle" equals "opened"
