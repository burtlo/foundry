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
    When I invoke "run advance" with flags "--step-budget 1"
    Then the CLI succeeds with:
      | field | expected |
      | active_node_id | execute.commit |
      | reason | engine_gate_resolved |

  Scenario: Gate decide is denied on engine gate
    Given run fixture "porcelain-0007-v009-execute-test-gate" in temporary workspace
    And execute workspace has app manifest and clean git
    When I invoke "gate decide" with decision "pass"
    Then the CLI fails with error "CAPABILITY_DENIED"

  Scenario: Run context for execute.test.gate opened visit
    Given run fixture "porcelain-0007-v009-execute-test-gate" in temporary workspace
    And execute workspace has app manifest and clean git
    When I invoke "run context"
    Then the CLI succeeds
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
