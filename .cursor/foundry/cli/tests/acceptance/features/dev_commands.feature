Feature: foundry dev shortcuts
  Developer workflow aliases for documentation generation, unit tests, and acceptance tests.
  These commands wrap the underlying Python library and pytest invocations.

  Background:
    Given workspace is the repository root

  Scenario: dev docs smoke-generates shape.intake documentation
    Given dev docs output directory is a temporary directory
    When I invoke "dev docs" with flags "--smoke"
    Then the CLI succeeds
    And file exists at response field "output_dir" relative "nodes/shape.intake.md"

  Scenario: dev unit runs the unit test suite
    When I invoke "dev unit" with flag "--quiet"
    Then the CLI succeeds with:
      | field | expected |
      | suite | unit |

  Scenario: dev acceptance runs the acceptance test suite
    When I invoke "dev acceptance" with flag "--quiet"
    Then the CLI succeeds with:
      | field | expected |
      | suite | acceptance |

  Scenario: dev all runs unit and acceptance suites
    When I invoke "dev all" with flag "--quiet"
    Then the CLI succeeds with:
      | field | expected |
      | suite | all |
    And response suites passed include "unit"
    And response suites passed include "acceptance"
