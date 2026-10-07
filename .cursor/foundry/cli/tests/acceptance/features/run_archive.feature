@foundry.run.archive
Feature: Run archive
  As a repository steward
  I want to archive completed runs into the Foundry runs store
  So that multiple runs with the same engine run id get unique archive folders

  Background:
    Given the foundry registry flow "implementation"

  Scenario: Run archive dry-run allocates next archive slug
    Given a temporary archive workspace with a completed run "porcelain-0001"
    And the foundry runs store contains archive "porcelain-0001"
    When I invoke "run archive" with flag "--dry-run"
    Then the CLI succeeds with:
      | field | expected |
      | dry_run | True |
      | archive_slug | porcelain-0002 |
      | run_id | porcelain-0001 |
    And workspace run directory "porcelain-0001" still exists

  Scenario: Run archive moves run and writes manifest
    Given a temporary archive workspace with a completed run "porcelain-0001"
    When I invoke "run archive"
    Then the CLI succeeds with:
      | field | expected |
      | archive_slug | porcelain-0001 |
      | removed_source | True |
    And workspace run directory "porcelain-0001" does not exist
    And archived run "porcelain-0001" contains "archive/manifest.json"
