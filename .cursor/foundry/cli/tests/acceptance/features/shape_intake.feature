@node.shape.intake
Feature: shape.intake vertical slice
  As a shape steward
  I want engine-owned intake completion for shape.intake
  So that tickets and receipts are sealed without manual publish or transition

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Deterministic intake completes without worker
    When I invoke "run create"
    Then the CLI succeeds
    And I store run id from response field "run_id"
    When I invoke visit intake complete with work prompt "Add shape intake vertical slice"
    Then the CLI succeeds with:
      | field | expected |
      | intake_status | passed |
      | transitioned | True |
      | next_node_id | shape.examine |
    When I invoke "run context"
    Then the CLI succeeds
    And context fields match:
      | field     | expected      |
      | node_id   | shape.examine |
      | lifecycle | opened        |

  Scenario: Missing work prompt seals blocked intake without transition
    When I invoke "run create"
    Then the CLI succeeds
    And I store run id from response field "run_id"
    When I invoke "visit intake complete"
    Then the CLI succeeds with:
      | field | expected |
      | intake_status | blocked |
      | block_reason | WORK_PROMPT_MISSING |
      | transitioned | False |
    When I invoke "visit transition" with summary "Should be blocked"
    Then the CLI fails with error "CAPABILITY_DENIED"

  Scenario: Re-run intake after blocked with work prompt succeeds
    When I invoke "run create"
    Then the CLI succeeds
    And I store run id from response field "run_id"
    When I invoke "visit intake complete"
    Then the CLI succeeds with:
      | field | expected |
      | intake_status | blocked |
    When I invoke visit intake complete with work prompt "Retry after block"
    Then the CLI succeeds with:
      | field | expected |
      | intake_status | passed |
      | next_node_id | shape.examine |

  Scenario: Denied steward capabilities on shape.intake
    When I invoke "run create"
    Then the CLI succeeds
    And I store run id from response field "run_id"
    When I invoke "artifact publish" with artifact "ticket" from "run:ticket.json"
    Then the CLI fails with error "CAPABILITY_DENIED"
    When I invoke "receipt seal" with schema "registry:schemas/intake-receipt.schema.json" file "run:receipts/intake.json"
    Then the CLI fails with error "CAPABILITY_DENIED"
    When I invoke "visit transition" with summary "Manual transition"
    Then the CLI fails with error "CAPABILITY_DENIED"

  Scenario: Run create with missing app manifest halts run
    Given a temporary workspace without app manifest
    When I invoke "run create"
    Then the CLI succeeds with:
      | field | expected |
      | status | halted |
      | active_lifecycle | examined |

  Scenario: Capability denied on wrong node
    When I invoke "run create"
    Then the CLI succeeds
    And I store run id from response field "run_id"
    When I invoke visit intake complete with work prompt "Advance to examine"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.examine |
    When I invoke "artifact publish" with artifact "ticket" from "run:ticket.json"
    Then the CLI fails with error "CAPABILITY_DENIED"

  Scenario: Mutating command rejected when visit not opened
    Given run fixture "porcelain-0007-v001-examined"
    When I invoke "visit state patch" with set '{"app_folder": "."}'
    Then the CLI fails with error "VISIT_NOT_OPENED"

  Scenario: Ledger show and run context are read-only
    Given run fixture "porcelain-0007-v001"
    And I record ledger event count
    When I invoke "ledger show" with types "check.recorded"
    Then the CLI succeeds
    When I invoke "run context"
    Then the CLI succeeds
    And ledger event count is unchanged

  Scenario: cli resolve returns registry and workspace paths
    When I invoke "cli resolve"
    Then the CLI succeeds
    And response field "registry_root" exists as directory
    And response field "workspace" exists as directory
    And response field "cli_path" exists as file
