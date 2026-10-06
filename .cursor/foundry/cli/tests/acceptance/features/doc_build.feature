@node.shape.intake
Feature: foundry doc build
  As an operator
  I want generated node documentation from the flow registry
  So that stewards can browse node references without hand-maintaining duplicates

  Background:
    Given the foundry registry flow "implementation"
    And workspace is the repository root

  Scenario: Build shape.intake documentation to a temporary directory
    Given doc output directory is a temporary directory
    When I invoke "doc build" for node "shape.intake" with output directory
    Then the CLI exit code is 0
    And generated node doc exists for node "shape.intake"
    And generated node doc for node "shape.intake" contains "#### Ticket fields"
    And generated node doc for node "shape.intake" contains "#### Downstream consumption"
    And generated node doc for node "shape.intake" contains "## Ledger excerpt"
    And generated cli doc exists for command "run-context"
    And generated cli index contains "`run.context`"
    And generated cli doc exists for command "shape"
    And generated cli doc exists for command "host-start"
    And generated cli index contains "`shape`"
    And generated cli index contains "`host start`"

  Scenario: Build full flow documentation from factory-flow.yaml
    Given doc output directory is a temporary directory
    When I invoke "doc build" with output directory
    Then the CLI exit code is 0
    And generated flow doc exists
    And generated flow doc contains "## Graph"
    And generated index exists
    And generated index contains "Flow graph and connections"
