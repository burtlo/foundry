@node.verify.intake
Feature: Stub execute advances to verify.intake
  With stub execute enabled, local start and run advance pass build/test gates into verify.

  Scenario: Passing stub verification advances through execute into verify
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    And execute workspace has app manifest and clean git
    And execute stub verification passes
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
    When I invoke "run advance"
    Then the CLI succeeds with:
      | field | expected |
      | active_node_id | verify.intake |
