Feature: foundry dev shortcuts
  Developer workflow aliases for documentation generation, unit tests, and acceptance tests.
  These commands wrap the underlying Python library and pytest invocations.

  Background:
    Given workspace is the repository root

  Scenario: dev docs smoke-generates shape.intake documentation
    Given dev docs output directory is a temporary directory
    When I invoke "dev docs" with json output and flags "--smoke"
    Then the CLI exit code is 0
    And response ok is true
    And file exists at response field "output_dir" relative "nodes/shape.intake.md"

  Scenario: dev unit runs the unit test suite
    When I invoke "dev unit" with json output and flag "--quiet"
    Then the CLI exit code is 0
    And response ok is true
    And response field "suite" equals "unit"

  Scenario: dev acceptance runs the acceptance test suite
    When I invoke "dev acceptance" with json output and flag "--quiet"
    Then the CLI exit code is 0
    And response ok is true
    And response field "suite" equals "acceptance"

  Scenario: dev all runs unit and acceptance suites
    When I invoke "dev all" with json output and flag "--quiet"
    Then the CLI exit code is 0
    And response ok is true
    And response field "suite" equals "all"
    And response suites passed include "unit"
    And response suites passed include "acceptance"
