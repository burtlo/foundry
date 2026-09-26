@node.shape.record
Feature: shape.record vertical slice
  As a shape steward
  I want mutating CLI commands for shape.record
  So that I can publish plan, seal agent receipt, and transition to shape.record.gate

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Happy path routes to shape.record.gate
    Given run fixture "porcelain-0007-v006-record" in temporary workspace
    When I write record plan draft to the run directory
    And I write record agent receipt draft to the run directory
    When I invoke "ledger show" with json output and types "check.recorded"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "visit state patch" with json output and set '{"approved_ac": "User can publish plan markdown.", "approved_ac_version": 1, "approved_ac_digest": "sha256:abc123", "plan_path": "run:artifacts/v-006/plan.md", "plan_version": 1}'
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "artifact publish" with json output and artifact "plan" from "run:artifacts/v-006/plan.md"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    And response ok is true
    When I invoke "visit transition" with json output and summary "Shape record complete"
    Then the CLI exit code is 0
    And response ok is true
    And response field "next_node_id" equals "shape.record.gate"
    And response field "next_lifecycle" equals "opened"

  Scenario: Blocked path seals agent receipt without publish or transition
    Given run fixture "porcelain-0007-v006-record" in temporary workspace
    When I write blocked record agent receipt draft to the run directory
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
      | field     | expected     |
      | node_id   | shape.record |
      | lifecycle | opened       |

  Scenario: Transition without approved_ac_version fails on seal
    Given run fixture "porcelain-0007-v006-record" in temporary workspace
    When I write record plan draft to the run directory
    And I write record agent receipt draft to the run directory
    When I invoke "visit state patch" with json output and set '{"approved_ac": "User can publish plan markdown.", "approved_ac_digest": "sha256:abc123", "plan_path": "run:artifacts/v-006/plan.md", "plan_version": 1}'
    Then the CLI exit code is 0
    When I invoke "artifact publish" with json output and artifact "plan" from "run:artifacts/v-006/plan.md"
    Then the CLI exit code is 0
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    When I invoke "visit transition" with json output and summary "Missing approved_ac_version"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CHECK_FAILED"

  Scenario: Transition without plan published fails on_close
    Given run fixture "porcelain-0007-v006-record" in temporary workspace
    When I write record agent receipt draft to the run directory
    When I invoke "visit state patch" with json output and set '{"approved_ac": "User can publish plan markdown.", "approved_ac_version": 1, "approved_ac_digest": "sha256:abc123", "plan_path": "run:artifacts/v-006/plan.md", "plan_version": 1}'
    Then the CLI exit code is 0
    When I invoke "receipt seal" with json output schema "registry:schemas/agent-receipt.schema.json" file "run:receipts/agent.json"
    Then the CLI exit code is 0
    When I invoke "visit transition" with json output and summary "Missing plan"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "ARTIFACT_INCOMPLETE"

  Scenario: Transition without agent receipt reopens visit
    Given run fixture "porcelain-0007-v006-record" in temporary workspace
    When I write record plan draft to the run directory
    When I invoke "visit state patch" with json output and set '{"approved_ac": "User can publish plan markdown.", "approved_ac_version": 1, "approved_ac_digest": "sha256:abc123", "plan_path": "run:artifacts/v-006/plan.md", "plan_version": 1}'
    Then the CLI exit code is 0
    When I invoke "artifact publish" with json output and artifact "plan" from "run:artifacts/v-006/plan.md"
    Then the CLI exit code is 0
    When I invoke "visit transition" with json output and summary "Missing agent receipt"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CHECK_FAILED"

  Scenario: on_examine failure halts run without prior present sealed
    Given run fixture "porcelain-0007-v006-record-examined"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field     | expected     |
      | node_id   | shape.record |
      | lifecycle | examined     |
    And the run snapshot status is "halted"

  Scenario: Gate decide on step is capability denied
    Given run fixture "porcelain-0007-v006-record" in temporary workspace
    When I invoke "gate decide" with json output and decision "record"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CAPABILITY_DENIED"

  Scenario: Run context for shape.record opened visit
    Given run fixture "porcelain-0007-v006-record"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field                              | expected                                     |
      | node_id                            | shape.record                                 |
      | visit_id                           | v-006                                        |
      | lifecycle                          | opened                                       |
      | instructions                       | registry:nodes/shape.record/instructions.md  |
      | instructions_path                  | (file exists)                                |
    And context allow cli equals:
      | capability        |
      | artifact.publish  |
      | ledger.show       |
      | receipt.link      |
      | transition        |
      | visit.state_patch |
    And context allow files write uris include:
      | uri                                 |
      | run:artifacts/v-006/plan.md         |
      | workspace:plan.md                   |
      | run:receipts/agent.json             |
    And context allow state includes "approved_ac"
    And context allow state includes "approved_ac_version"
