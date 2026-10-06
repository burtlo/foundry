Feature: Durable run storage and host idempotency
  Per-run ledger events append to ledger.jsonl before snapshot.json is replaced.
  Inline ledger[] in the snapshot remains for existing readers; storage_version 2 marks migrated runs.
  Host mutation idempotency keys persist under .foundry/host/idempotency.json across process restarts.

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Local advance commits events to ledger.jsonl
    When I invoke "run create" with json output and work prompt "Ledger durability proof"
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    When I invoke "run advance" with json output and flag "--local"
    Then the CLI exit code is 0
    And the current run has a ledger.jsonl file
    And the run snapshot has storage version 2
    And inline ledger matches ledger.jsonl event count

  Scenario: Legacy inline-only snapshot migrates on load
    Given a legacy inline-only run in the workspace
    When I invoke "run get" with json output and flag "--local"
    Then the CLI exit code is 0
    And the current run has a ledger.jsonl file
    And the run snapshot has storage version 2
    And inline ledger matches ledger.jsonl event count

  Scenario: Foreground host persists mutation idempotency keys
    Given the foreground job host is running for the workspace
    When I invoke "run create" with json output and work prompt "Idempotency proof"
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    When I invoke "run advance" with json output
    Then the CLI exit code is 0
    And workspace host idempotency store file exists
