@node.shape.intake
Feature: shape.intake vertical slice
  As a shape steward
  I want engine-owned intake completion for shape.intake
  So that tickets and receipts are sealed without manual publish or transition

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Deterministic intake completes without worker
    When I invoke "run create" with json output
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    When I invoke visit intake complete with work prompt "Add shape intake vertical slice"
    Then the CLI exit code is 0
    And response ok is true
    And response field "intake_status" equals "passed"
    And response field "transitioned" equals "True"
    And response field "next_node_id" equals "shape.examine"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And context fields match:
      | field     | expected      |
      | node_id   | shape.examine |
      | lifecycle | opened        |

  Scenario: Missing work prompt seals blocked intake without transition
    When I invoke "run create" with json output
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    When I invoke "visit intake complete" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "intake_status" equals "blocked"
    And response field "block_reason" equals "WORK_PROMPT_MISSING"
    And response field "transitioned" equals "False"
    When I invoke "visit transition" with json output and summary "Should be blocked"
    Then the CLI exit code is 1
    And response error code equals "CAPABILITY_DENIED"

  Scenario: Re-run intake after blocked with work prompt succeeds
    When I invoke "run create" with json output
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    When I invoke "visit intake complete" with json output
    Then the CLI exit code is 0
    And response field "intake_status" equals "blocked"
    When I invoke visit intake complete with work prompt "Retry after block"
    Then the CLI exit code is 0
    And response field "intake_status" equals "passed"
    And response field "next_node_id" equals "shape.examine"

  Scenario: Denied steward capabilities on shape.intake
    When I invoke "run create" with json output
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    When I invoke "artifact publish" with json output and artifact "ticket" from "run:ticket.json"
    Then the CLI exit code is 1
    And response error code equals "CAPABILITY_DENIED"
    When I invoke "receipt seal" with json output schema "registry:schemas/intake-receipt.schema.json" file "run:receipts/intake.json"
    Then the CLI exit code is 1
    And response error code equals "CAPABILITY_DENIED"
    When I invoke "visit transition" with json output and summary "Manual transition"
    Then the CLI exit code is 1
    And response error code equals "CAPABILITY_DENIED"

  Scenario: Run create with missing app manifest halts run
    Given a temporary workspace without app manifest
    When I invoke "run create" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "status" equals "halted"
    And response field "active_lifecycle" equals "examined"

  Scenario: Capability denied on wrong node
    When I invoke "run create" with json output
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    When I invoke visit intake complete with work prompt "Advance to examine"
    Then the CLI exit code is 0
    And response field "next_node_id" equals "shape.examine"
    When I invoke "artifact publish" with json output and artifact "ticket" from "run:ticket.json"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CAPABILITY_DENIED"

  Scenario: Mutating command rejected when visit not opened
    Given run fixture "porcelain-0007-v001-examined"
    When I invoke "visit state patch" with json output and set '{"app_folder": "."}'
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "VISIT_NOT_OPENED"

  Scenario: Ledger show and run context are read-only
    Given run fixture "porcelain-0007-v001"
    And I record ledger event count
    When I invoke "ledger show" with json output and types "check.recorded"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And ledger event count is unchanged

  Scenario: cli resolve returns registry and workspace paths
    When I invoke "cli resolve" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "registry_root" exists as directory
    And response field "workspace" exists as directory
    And response field "cli_path" exists as file
