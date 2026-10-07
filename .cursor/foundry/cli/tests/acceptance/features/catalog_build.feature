@node.shape.intake
Feature: foundry catalog build
  As an operator
  I want machine-readable node index files generated from flows/implementation/registry.yaml
  So that tools can inspect nodes without parsing the full flow registry

  Read-only: this command must not append ledger events.

  Background:
    Given the foundry registry flow "implementation"
    And workspace is the repository root

  Scenario: Build all node indexes under the default catalog directory
    Given catalog output directory is a temporary directory
    When I invoke "catalog build" with output directory
    Then the CLI exit code is 0
    And catalog summary node count equals 29
    And catalog index file exists for node "shape.intake"
    And catalog index for node "shape.intake" fields match:
      | field                              | expected                                              |
      | node_id                            | shape.intake                                          |
      | flow_id                            | implementation                                        |
      | kind                               | step                                                  |
      | entry                              | true                                                  |
      | terminal                           | false                                                 |
      | assets.receipts[0]                 | registry:schemas/intake-receipt.schema.json           |
      | assets.receipts[1]                 | registry:schemas/agent-receipt.schema.json            |
      | assets.artifacts[0].id             | ticket                                                |
      | assets.artifacts[0].schema         | registry:schemas/ticket.schema.json                   |
      | connections.out[0].id              | shape.intake-to-shape.examine                         |
      | connections.out[0].to              | shape.examine                                         |
      | checks_used.on_open[0]             | validate-manifest                                     |
      | checks_used.on_seal[0]             | intake-receipt-sealed                                 |
      | checks_used.on_seal[1]             | agent-receipt-sealed                                  |
    And catalog index for node "shape.intake" tests include ".cursor/foundry/cli/tests/acceptance/features/run_context.feature"

  Scenario: Build a single node index
    Given catalog output directory is a temporary directory
    When I invoke "catalog build" for node "shape.intake" with output directory
    Then the CLI exit code is 0
    And catalog summary node count equals 1
    And catalog index file exists for node "shape.intake"
    And catalog index file does not exist for node "shape.examine"

  Scenario: Json output returns summary without writing files
    When I invoke "catalog build" for node "shape.intake" with json output
    Then the CLI exit code is 0
    And response ok is true
    And response catalog index for node "shape.intake" is present
    And default catalog index file does not exist for node "shape.intake"

  Scenario: Unknown node id fails
    When I invoke "catalog build" for node "does.not.exist" with json output
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "NODE_NOT_FOUND"
