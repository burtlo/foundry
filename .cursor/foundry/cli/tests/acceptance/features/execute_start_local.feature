@node.execute.start
Feature: Local execute.start reaches execute.build
  After shape.record.gate accept, steward starts execute without host and lands on execute.build.

  Scenario: Advance from execute.intake to execute.build boundary
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    And execute workspace has app manifest and clean git
    When I invoke "gate decide" with decision "accept"
    Then the CLI succeeds
    When I invoke "run advance"
    Then the CLI succeeds with:
      | field | expected |
      | active_node_id | execute.start |
    And execute workspace has app manifest and clean git
    When I invoke "start" with flags "--no-host --local"
    Then the CLI succeeds with:
      | field | expected |
      | active_node_id | execute.build |
      | wait | None |
