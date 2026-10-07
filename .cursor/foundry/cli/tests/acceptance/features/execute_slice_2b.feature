@workflow.execute.slice_2b
Feature: Execute slice 2B build/test/repair
  Workflow-02 host path through execute.test.gate and repair limit.

  Scenario: Passing stub verification advances through execute into verify
    Given run fixture "porcelain-0007-v007-record-gate" in temporary workspace
    And execute workspace has app manifest and clean git
    And execute stub verification passes
    When I invoke "gate decide" with json output and decision "accept"
    Then the CLI exit code is 0
    When I invoke "run advance" with json output
    Then the CLI exit code is 0
    And response field "active_node_id" equals "execute.start"
    And execute workspace has app manifest and clean git
    When I invoke "start" with json output and flags "--no-host --local"
    Then the CLI exit code is 0
    And response field "active_node_id" equals "execute.build"
    When I invoke "run advance" with json output
    Then the CLI exit code is 0
    And response field "active_node_id" equals "verify.intake"
