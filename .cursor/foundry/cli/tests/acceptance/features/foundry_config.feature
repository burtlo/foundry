@foundry.config
Feature: Foundry registry config
  As a repository steward
  I want to initialize and validate .foundry/foundry.yaml
  So that Foundry resolves the registry bundle without symlinking .cursor/foundry

  Background:
    Given the foundry registry flow "implementation"

  Scenario: Config init dry-run writes nothing
    Given a temporary config workspace without foundry.yaml
    When I invoke "config init" with flag "--dry-run"
    Then the CLI succeeds with:
      | field | expected |
      | written | False |
      | dry_run | True |
    And workspace foundry config file does not exist

  Scenario: Config init writes foundry.yaml
    Given a temporary config workspace without foundry.yaml
    When I invoke "config init"
    Then the CLI succeeds with:
      | field | expected |
      | written | True |
    And workspace foundry config file exists

  Scenario: Config validate passes when registry resolves
    Given a temporary config workspace with foundry.yaml pointing at bundle
    When I invoke "config validate"
    Then the CLI succeeds with:
      | field | expected |
      | valid | True |

  Scenario: Config validate fails on missing registry target
    Given a temporary config workspace with invalid foundry.yaml registry
    When I invoke "config validate"
    Then the CLI fails with error "FOUNDRY_CONFIG_INVALID"

  Scenario: Cli resolve returns registry_source foundry.yaml when configured
    Given a temporary config workspace with foundry.yaml pointing at bundle
    And cli resolve omits global registry flag
    When I invoke "cli resolve"
    Then the CLI succeeds with:
      | field | expected |
      | registry_source | foundry.yaml |

  Scenario: Cli resolve works without global registry when foundry.yaml present
    Given a temporary config workspace with foundry.yaml pointing at bundle
    And cli resolve omits global registry flag
    When I invoke "cli resolve"
    Then the CLI succeeds
    And response field "registry_root" exists as directory
    And response field "cli_path" exists as file

  Scenario: Cli resolve returns cli_path relative to workspace when bundle is inside workspace
    Given a temporary config workspace with foundry.yaml pointing at in-workspace bundle
    And cli resolve omits global registry flag
    When I invoke "cli resolve"
    Then the CLI succeeds with:
      | field | expected |
      | cli_path | bundle/cli/foundry.sh |
