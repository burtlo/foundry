@app.bootstrap
Feature: Application manifest bootstrap
  As a repository steward
  I want to discover, initialize, and validate .foundry/app.yaml
  So that Foundry runs can bootstrap against application mechanics

  Background:
    Given the foundry registry flow "implementation"

  Scenario: Discover proposes a manifest for Makefile and go.mod workspace
    Given a temporary bootstrap workspace with Makefile and go.mod
    When I invoke "app discover"
    Then the CLI succeeds with:
      | field | expected |
      | proposed_manifest.schema_version | 1 |
      | proposed_manifest.id | bootstrap-app |
      | proposed_manifest.commands.build.default.argv[0] | make |
      | proposed_manifest.builders.default_owner | general-builder |

  Scenario: Init dry-run validates without writing
    Given a temporary bootstrap workspace without manifest
    And a manifest input file with sample bootstrap manifest
    When I invoke "app init" with flag "--dry-run"
    Then the CLI succeeds with:
      | field | expected |
      | written | False |
      | dry_run | True |
    And workspace manifest file does not exist

  Scenario: Init writes manifest from input file
    Given a temporary bootstrap workspace without manifest
    And a manifest input file with sample bootstrap manifest
    When I invoke "app init"
    Then the CLI succeeds with:
      | field | expected |
      | written | True |
    And workspace manifest file exists with id "sample-app"

  Scenario: Validate passes on written manifest
    Given a temporary bootstrap workspace without manifest
    And a manifest input file with sample bootstrap manifest
    When I invoke "app init"
    Then the CLI succeeds
    When I invoke "app validate"
    Then the CLI succeeds with:
      | field | expected |
      | valid | True |
      | manifest_id | sample-app |

  Scenario: Init without force fails when manifest differs
    Given a temporary bootstrap workspace without manifest
    And a manifest input file with sample bootstrap manifest
    When I invoke "app init"
    Then the CLI succeeds
    Given a manifest input file with alternate bootstrap manifest id "replacement-app"
    When I invoke "app init"
    Then the CLI fails with error "APP_MANIFEST_EXISTS"
    And workspace manifest file exists with id "sample-app"

  Scenario: Init is idempotent when content matches
    Given a temporary bootstrap workspace without manifest
    And a manifest input file with sample bootstrap manifest
    When I invoke "app init"
    Then the CLI succeeds
    When I invoke "app init"
    Then the CLI succeeds with:
      | field | expected |
      | changed | False |
      | written | False |
