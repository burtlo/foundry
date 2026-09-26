@app.bootstrap
Feature: Application manifest bootstrap
  As a repository steward
  I want to discover, initialize, and validate .foundry/app.yaml
  So that Foundry runs can bootstrap against application mechanics

  Background:
    Given the foundry registry flow "implementation"

  Scenario: Discover proposes a manifest for Makefile and go.mod workspace
    Given a temporary bootstrap workspace with Makefile and go.mod
    When I invoke "app discover" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "proposed_manifest.schema_version" equals "1"
    And response field "proposed_manifest.id" equals "bootstrap-app"
    And response field "proposed_manifest.commands.build.default.argv[0]" equals "make"
    And response field "proposed_manifest.builders.default_owner" equals "general-builder"

  Scenario: Init dry-run validates without writing
    Given a temporary bootstrap workspace without manifest
    And a manifest input file with sample bootstrap manifest
    When I invoke "app init" with json output and flag "--dry-run"
    Then the CLI exit code is 0
    And response ok is true
    And response field "written" equals "False"
    And response field "dry_run" equals "True"
    And workspace manifest file does not exist

  Scenario: Init writes manifest from input file
    Given a temporary bootstrap workspace without manifest
    And a manifest input file with sample bootstrap manifest
    When I invoke "app init" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "written" equals "True"
    And workspace manifest file exists with id "sample-app"

  Scenario: Validate passes on written manifest
    Given a temporary bootstrap workspace without manifest
    And a manifest input file with sample bootstrap manifest
    When I invoke "app init" with json output
    Then the CLI exit code is 0
    When I invoke "app validate" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "valid" equals "True"
    And response field "manifest_id" equals "sample-app"

  Scenario: Init without force fails when manifest differs
    Given a temporary bootstrap workspace without manifest
    And a manifest input file with sample bootstrap manifest
    When I invoke "app init" with json output
    Then the CLI exit code is 0
    Given a manifest input file with alternate bootstrap manifest id "replacement-app"
    When I invoke "app init" with json output
    Then the CLI exit code is 1
    And response error code equals "APP_MANIFEST_EXISTS"
    And workspace manifest file exists with id "sample-app"

  Scenario: Init is idempotent when content matches
    Given a temporary bootstrap workspace without manifest
    And a manifest input file with sample bootstrap manifest
    When I invoke "app init" with json output
    Then the CLI exit code is 0
    When I invoke "app init" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "changed" equals "False"
    And response field "written" equals "False"
