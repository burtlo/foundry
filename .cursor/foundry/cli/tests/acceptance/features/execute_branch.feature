@node.execute.branch
Feature: execute.branch vertical slice
  As an execute steward
  I want run advance to create the feature branch
  So that execute.plan runs on an isolated git branch after intake gate

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Run advance after intake gate creates branch and routes to execute.plan
    Given run fixture "porcelain-0007-v008-execute-intake-gate" in temporary workspace
    And execute workspace has app manifest and clean git
    When I invoke "run advance" with flags "--step-budget 2"
    Then the CLI succeeds with:
      | field | expected |
      | active_node_id | execute.plan |
      | reason | execute_branch_complete |
