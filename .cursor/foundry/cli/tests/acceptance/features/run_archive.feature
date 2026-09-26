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
    When I invoke "run archive" with json output and flag "--dry-run"
    Then the CLI exit code is 0
    And response ok is true
    And response field "dry_run" equals "True"
    And response field "archive_slug" equals "porcelain-0002"
    And response field "run_id" equals "porcelain-0001"
    And workspace run directory "porcelain-0001" still exists

  Scenario: Run archive moves run and writes manifest
    Given a temporary archive workspace with a completed run "porcelain-0001"
    When I invoke "run archive" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "archive_slug" equals "porcelain-0001"
    And response field "removed_source" equals "True"
    And workspace run directory "porcelain-0001" does not exist
    And archived run "porcelain-0001" contains "archive/manifest.json"
