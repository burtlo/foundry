@node.shape.examine
Feature: shape.examine vertical slice
  As a shape steward
  I want engine-owned examination completion
  So that agent judgment seals receipts and routes to present or gate without manual orchestration

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Fast lane happy path routes to shape.present
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I prepare shape examine agent wait without auto submit
    When I submit examination result with no open questions
    Then the CLI exit code is 0
    When I invoke visit examine complete with json output
    Then the CLI exit code is 0
    And response ok is true
    And response field "next_node_id" equals "shape.present"
    And response field "next_lifecycle" equals "opened"

  Scenario: Gate path routes to shape.examine.gate when open questions remain
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I prepare shape examine agent wait without auto submit
    When I submit examination result with one open question
    Then the CLI exit code is 0
    When I invoke visit examine complete with open questions gate path
    Then the CLI exit code is 0
    And response ok is true
    And response field "next_node_id" equals "shape.examine.gate"
    And response field "next_lifecycle" equals "opened"

  Scenario: Complete without judgment fails
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I invoke visit examine complete with json output
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "JUDGMENT_MISSING"

  Scenario: Complete with open questions without gate flag fails
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I prepare shape examine agent wait without auto submit
    When I submit examination result with one open question
    Then the CLI exit code is 0
    When I invoke visit examine complete with json output
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "OPEN_QUESTIONS_PENDING"

  Scenario: on_examine failure halts run at examined lifecycle
    Given run fixture "porcelain-0007-v002-examine-examined"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field     | expected      |
      | node_id   | shape.examine |
      | lifecycle | examined      |
    And the run snapshot status is "halted"

  Scenario: Visit state patch denied on shape.examine
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I invoke "visit state patch" with json output and set '{"ticket": "override"}'
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CAPABILITY_DENIED"

  Scenario: Transition denied on shape.examine
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I invoke "visit transition" with json output and summary "Manual transition"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CAPABILITY_DENIED"

  Scenario: Mutating command rejected when lifecycle examined
    Given run fixture "porcelain-0007-v002-examine-examined"
    When I invoke visit examine complete with json output
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "VISIT_NOT_OPENED"

  Scenario: Run context for shape.examine opened visit
    Given run fixture "porcelain-0007-v002-examine"
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field                              | expected                                     |
      | node_id                            | shape.examine                                |
      | visit_id                           | v-002                                        |
      | lifecycle                          | opened                                       |
      | instructions                       | registry:nodes/shape.examine/judgment.md |
      | instructions_path                  | (file exists)                                |
      | reads.artifacts[0].artifact        | shape.intake.ticket                          |
      | reads.artifacts[0].from            | nearest_sealed_ancestor                      |
    And context allow cli equals:
      | capability              |
      | run.agent.submit        |
      | visit.examine.complete  |
    And context allow user ask is false

  Scenario: End-to-end from run create through examine complete
    When I invoke "run create" with json output
    Then the CLI exit code is 0
    And I store run id from response field "run_id"
    When I invoke "visit state patch" with json output and set '{"app_folder": "."}'
    Then the CLI exit code is 0
    When I invoke visit intake complete with work prompt "E2E shape phase work request"
    Then the CLI exit code is 0
    And response field "next_node_id" equals "shape.examine"
    When I prepare shape examine agent wait without auto submit
    When I submit examination result with no open questions
    Then the CLI exit code is 0
    When I invoke visit examine complete with json output
    Then the CLI exit code is 0
    And response field "next_node_id" equals "shape.present"
