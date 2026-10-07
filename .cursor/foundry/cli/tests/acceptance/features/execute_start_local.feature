@node.execute.start
Feature: Local execute.start reaches execute.build
  After shape.record.gate accept, steward starts execute without host and lands on execute.build.

  Scenario: Advance from execute.intake to execute.build boundary
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    And execute workspace has app manifest and clean git
    When I invoke "gate decide" with json output and decision "accept"
    Then the CLI exit code is 0
    When I invoke "run advance" with json output
    Then the CLI exit code is 0
    And response field "active_node_id" equals "execute.start"
    And execute workspace has app manifest and clean git
    When I invoke "start" with json output and flags "--no-host --local"
    Then the CLI exit code is 0
    And response field "active_node_id" equals "execute.build"
    And response field "wait" equals "None"
