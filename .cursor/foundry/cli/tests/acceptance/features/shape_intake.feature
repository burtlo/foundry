@node.shape.intake
Feature: shape.intake vertical slice
  As a shape steward
  I want mutating CLI commands for shape.intake
  So that I can publish artifacts, seal receipts, and transition to shape.examine

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Happy path from run create through transition to shape.examine
    When I invoke "run create" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "active_lifecycle" equals "opened"
    And I store run id from response field "run_id"
    When I invoke "visit state patch" with json output and set '{"app_folder": "."}'
    Then the CLI exit code is 0
    And response ok is true
    And I write ticket draft to the run directory
    And I write receipt drafts to the run directory
    When I invoke "ledger show" with json output and types "check.recorded"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "artifact publish" with json output and artifact "ticket" from "run:ticket.json"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "receipt seal" with json output schema "registry:schemas/intake-receipt.schema.json" file "run:receipts/intake.json"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "visit transition" with json output and summary "Shape intake complete"
    Then the CLI exit code is 0
    And response ok is true
    And response field "next_node_id" equals "shape.examine"
    And response field "next_lifecycle" equals "opened"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And context fields match:
      | field     | expected      |
      | node_id   | shape.examine |
      | lifecycle | opened        |

  Scenario: Blocked path seals receipts without transition
    When I invoke "run create" with json output
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    And I write receipt drafts to the run directory
    When I invoke "ledger show" with json output and types "check.recorded"
    Then the CLI exit code is 0
    When I invoke "receipt seal" with json output schema "registry:schemas/intake-receipt.schema.json" file "run:receipts/intake.json"
    Then the CLI exit code is 0
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And context fields match:
      | field     | expected     |
      | node_id   | shape.intake |
      | lifecycle | opened       |
    And the run snapshot has no ledger event type "connection.taken"
    And the run snapshot has no ledger event type "visit.sealed"

  Scenario: Transition without published ticket fails on_close
    When I invoke "run create" with json output
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    And I write receipt drafts to the run directory
    When I invoke "receipt seal" with json output schema "registry:schemas/intake-receipt.schema.json" file "run:receipts/intake.json"
    Then the CLI exit code is 0
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    When I invoke "visit transition" with json output and summary "Should fail"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "ARTIFACT_INCOMPLETE"

  Scenario: Transition without required receipts reopens visit
    When I invoke "run create" with json output
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    And I write ticket draft to the run directory
    When I invoke "artifact publish" with json output and artifact "ticket" from "run:ticket.json"
    Then the CLI exit code is 0
    When I invoke "visit transition" with json output and summary "Missing receipts"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CHECK_FAILED"

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
    And I write ticket draft to the run directory
    And I write receipt drafts to the run directory
    When I invoke "artifact publish" with json output and artifact "ticket" from "run:ticket.json"
    Then the CLI exit code is 0
    When I invoke "receipt seal" with json output schema "registry:schemas/intake-receipt.schema.json" file "run:receipts/intake.json"
    Then the CLI exit code is 0
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    When I invoke "visit transition" with json output and summary "Advance to examine"
    Then the CLI exit code is 0
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
