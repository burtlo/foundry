@node.execute.intake.gate
Feature: execute.intake.gate vertical slice
  As an execute steward
  I want the engine intake gate to resolve from sealed intake evidence
  So that branching proceeds only after passed execute.intake

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Run advance passes gate and routes to execute.branch
    Given run fixture "porcelain-0007-v008-execute-intake-gate" in temporary workspace
    And execute workspace has app manifest and clean git
    When I invoke "run advance" with json output and flags "--step-budget 1"
    Then the CLI exit code is 0
    And response ok is true
    And response field "active_node_id" equals "execute.branch"
    And response field "reason" equals "engine_gate_resolved"

  Scenario: Gate decide is denied on engine gate
    Given run fixture "porcelain-0007-v008-execute-intake-gate" in temporary workspace
    And execute workspace has app manifest and clean git
    When I invoke "gate decide" with json output and decision "pass"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CAPABILITY_DENIED"

  Scenario: Run context for execute.intake.gate opened visit
    Given run fixture "porcelain-0007-v008-execute-intake-gate" in temporary workspace
    And execute workspace has app manifest and clean git
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field             | expected                                                        |
      | node_id           | execute.intake.gate                                             |
      | visit_id          | v-010                                                           |
      | kind              | gate                                                            |
      | lifecycle         | opened                                                          |
      | decider           | engine                                                          |
      | prompt            | Engine gate. Confirms the sealed execute.intake receipt status is passed before branching. |
      | reads.intake_receipt.status | passed                                                  |
    And context allow cli equals:
      | capability |
    And context produces options equal:
      | option |
      | pass   |
