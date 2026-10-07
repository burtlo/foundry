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
    Then the CLI succeeds
    When I invoke visit examine complete
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.present |
      | next_lifecycle | opened |

  Scenario: Gate path routes to shape.examine.gate when open questions remain
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I prepare shape examine agent wait without auto submit
    When I submit examination result with one open question
    Then the CLI succeeds
    When I invoke visit examine complete with open questions gate path
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.examine.gate |
      | next_lifecycle | opened |

  Scenario: Complete without judgment fails
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I invoke visit examine complete
    Then the CLI fails with error "JUDGMENT_MISSING"

  Scenario: Complete with open questions without gate flag fails
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I prepare shape examine agent wait without auto submit
    When I submit examination result with one open question
    Then the CLI succeeds
    When I invoke visit examine complete
    Then the CLI fails with error "OPEN_QUESTIONS_PENDING"

  Scenario: on_examine failure halts run at examined lifecycle
    Given run fixture "porcelain-0007-v002-examine-examined"
    When I invoke "run context"
    Then the CLI succeeds
    And context fields match:
      | field     | expected      |
      | node_id   | shape.examine |
      | lifecycle | examined      |
    And the run snapshot status is "halted"

  Scenario: Visit state patch denied on shape.examine
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I invoke "visit state patch" with set '{"ticket": "override"}'
    Then the CLI fails with error "CAPABILITY_DENIED"

  Scenario: Transition denied on shape.examine
    Given run fixture "porcelain-0007-v002-examine" in temporary workspace
    When I invoke "visit transition" with summary "Manual transition"
    Then the CLI fails with error "CAPABILITY_DENIED"

  Scenario: Mutating command rejected when lifecycle examined
    Given run fixture "porcelain-0007-v002-examine-examined"
    When I invoke visit examine complete
    Then the CLI fails with error "VISIT_NOT_OPENED"

  Scenario: Run context for shape.examine opened visit
    Given run fixture "porcelain-0007-v002-examine"
    When I invoke "run context"
    Then the CLI succeeds
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
    When I invoke "run create"
    Then the CLI succeeds
    And I store run id from response field "run_id"
    When I invoke "visit state patch" with set '{"app_folder": "."}'
    Then the CLI succeeds
    When I invoke visit intake complete with work prompt "E2E shape phase work request"
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.examine |
    When I prepare shape examine agent wait without auto submit
    When I submit examination result with no open questions
    Then the CLI succeeds
    When I invoke visit examine complete
    Then the CLI succeeds with:
      | field | expected |
      | next_node_id | shape.present |
