@foundry.config
Feature: Foundry registry config
  As a repository steward
  I want to initialize and validate .foundry/foundry.yaml
  So that Foundry resolves the registry bundle without symlinking .cursor/foundry

  Background:
    Given the foundry registry flow "implementation"

  Scenario: Config init dry-run writes nothing
    Given a temporary config workspace without foundry.yaml
    When I invoke "config init" with json output and flag "--dry-run"
    Then the CLI exit code is 0
    And response ok is true
    And response field "written" equals "False"
    And response field "dry_run" equals "True"
    And workspace foundry config file does not exist

  Scenario: Config init writes foundry.yaml
    Given a temporary config workspace without foundry.yaml
    When I invoke "config init" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "written" equals "True"
    And workspace foundry config file exists

  Scenario: Config validate passes when registry resolves
    Given a temporary config workspace with foundry.yaml pointing at bundle
    When I invoke "config validate" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "valid" equals "True"

  Scenario: Config validate fails on missing registry target
    Given a temporary config workspace with invalid foundry.yaml registry
    When I invoke "config validate" with json output
    Then the CLI exit code is 1
    And response error code equals "FOUNDRY_CONFIG_INVALID"

  Scenario: Cli resolve returns registry_source foundry.yaml when configured
    Given a temporary config workspace with foundry.yaml pointing at bundle
    And cli resolve omits global registry flag
    When I invoke "cli resolve" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "registry_source" equals "foundry.yaml"

  Scenario: Cli resolve works without global registry when foundry.yaml present
    Given a temporary config workspace with foundry.yaml pointing at bundle
    And cli resolve omits global registry flag
    When I invoke "cli resolve" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "registry_root" exists as directory
