@node.shape.present
Feature: shape.present vertical slice
  As a shape steward
  I want mutating CLI commands for shape.present
  So that I can publish presentation, seal agent receipt, and transition to shape.present.gate

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Happy path routes to shape.present.gate
    Given run fixture "porcelain-0007-v004-present" in temporary workspace
    When I write present presentation draft to the run directory
    And I write present agent receipt draft to the run directory
    When I invoke "ledger show" with json output and types "check.recorded"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "visit state patch" with json output and set '{"presented_ac": "User can publish presentation markdown.", "presentation_artifact_path": "run:artifacts/v-004/presentation.md"}'
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "artifact publish" with json output and artifact "presentation" from "run:artifacts/v-004/presentation.md"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "visit transition" with json output and summary "Shape presentation complete"
    Then the CLI exit code is 0
    And response ok is true
    And response field "next_node_id" equals "shape.present.gate"
    And response field "next_lifecycle" equals "opened"

  Scenario: Blocked path seals agent receipt without publish or transition
    Given run fixture "porcelain-0007-v004-present" in temporary workspace
    When I write blocked present agent receipt draft to the run directory
    When I invoke "ledger show" with json output and types "check.recorded"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field     | expected      |
      | node_id   | shape.present |
      | lifecycle | opened        |

  Scenario: Transition without presentation fails on_close
    Given run fixture "porcelain-0007-v004-present" in temporary workspace
    When I write present agent receipt draft to the run directory
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    When I invoke "visit transition" with json output and summary "Missing presentation"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "ARTIFACT_INCOMPLETE"

  Scenario: Transition without agent receipt reopens visit
    Given run fixture "porcelain-0007-v004-present" in temporary workspace
    When I write present presentation draft to the run directory
    When I invoke "artifact publish" with json output and artifact "presentation" from "run:artifacts/v-004/presentation.md"
    Then the CLI exit code is 0
    When I invoke "visit transition" with json output and summary "Missing agent receipt"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CHECK_FAILED"

  Scenario: on_examine failure halts run without prior examine sealed
    Given run fixture "porcelain-0007-v004-present-examined"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field     | expected      |
      | node_id   | shape.present |
      | lifecycle | examined      |
    And the run snapshot status is "halted"

  Scenario: Gate decide on step is capability denied
    Given run fixture "porcelain-0007-v004-present" in temporary workspace
    When I invoke "gate decide" with json output and decision "reject"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CAPABILITY_DENIED"

  Scenario: Artifact publish denied after transition to gate
    Given run fixture "porcelain-0007-v004-present" in temporary workspace
    When I write present presentation draft to the run directory
    And I write present agent receipt draft to the run directory
    When I invoke "artifact publish" with json output and artifact "presentation" from "run:artifacts/v-004/presentation.md"
    Then the CLI exit code is 0
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    When I invoke "visit transition" with json output and summary "Shape presentation complete"
    Then the CLI exit code is 0
    When I invoke "artifact publish" with json output and artifact "presentation" from "run:artifacts/v-004/presentation.md"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CAPABILITY_DENIED"

  Scenario: Mutating command rejected when lifecycle examined
    Given run fixture "porcelain-0007-v004-present-examined"
    When I invoke "visit state patch" with json output and set '{"presented_ac": "blocked"}'
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "VISIT_NOT_OPENED"

  Scenario: Run context for shape.present opened visit
    Given run fixture "porcelain-0007-v004-present"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field                              | expected                                         |
      | node_id                            | shape.present                                    |
      | visit_id                           | v-004                                            |
      | lifecycle                          | opened                                           |
      | instructions                       | registry:nodes/shape.present/instructions.md     |
      | instructions_path                  | (file exists)                                    |
    And context allow cli equals:
      | capability        |
      | artifact.publish  |
      | ledger.show       |
      | receipt.link      |
      | transition        |
      | visit.state_patch |
    And context allow files write uris include:
      | uri                                         |
      | run:artifacts/v-004/presentation.md         |
      | run:receipts/v-004/assessment.md            |
      | run:receipts/agent.json                     |
    And context allow state includes "state.nodes.shape.present.*"
