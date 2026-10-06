@node.execute.test.gate
Feature: execute.test.gate vertical slice
  As an execute steward
  I want the engine test gate to resolve from sealed verification evidence
  So that commit or repair routing follows receipt exit codes

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Run advance passes gate and routes to execute.commit
    Given run fixture "porcelain-0007-v009-execute-test-gate" in temporary workspace
    And execute workspace has app manifest and clean git
    When I invoke "run advance" with json output and flags "--step-budget 1"
    Then the CLI exit code is 0
    And response ok is true
    And response field "active_node_id" equals "execute.commit"
    And response field "reason" equals "engine_gate_resolved"

  Scenario: Gate decide is denied on engine gate
    Given run fixture "porcelain-0007-v009-execute-test-gate" in temporary workspace
    And execute workspace has app manifest and clean git
    When I invoke "gate decide" with json output and decision "pass"
    Then the CLI exit code is 1
    And response ok is false
    And response error code equals "CAPABILITY_DENIED"

  Scenario: Run context for execute.test.gate opened visit
    Given run fixture "porcelain-0007-v009-execute-test-gate" in temporary workspace
    And execute workspace has app manifest and clean git
    When I invoke "run context" with json output
    Then the CLI exit code is 0
    And response ok is true
    And context fields match:
      | field             | expected                                                        |
      | node_id           | execute.test.gate                                               |
      | kind              | gate                                                            |
      | lifecycle         | opened                                                          |
      | decider           | engine                                                          |
      | prompt            | Engine gate. Maps sealed execute.test agent receipt command exit codes to pass or repair. |
      | reads.test_receipt.commands[0].exit_code | 0                                     |
    And context allow cli equals:
      | capability |
    And context produces options equal:
      | option |
      | pass   |
      | repair |
