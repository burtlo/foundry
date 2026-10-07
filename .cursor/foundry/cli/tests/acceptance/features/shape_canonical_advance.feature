@shape.canonical
Feature: Shape canonical host advance path
  As a shape steward
  I want run advance to drive shape intake after work prompt is set
  So that the host path is canonical without manual intake-only shortcuts

  Background:
    Given the foundry registry flow "implementation"
    And a temporary workspace with valid app manifest

  Scenario: Run advance after create reaches present gate
    When I invoke "run create" with work prompt "Canonical advance shape work"
    Then the CLI succeeds
    And I store run id from response field "run_id"
    When I invoke "run advance" with flag "--local"
    Then the CLI succeeds with:
      | field | expected |
      | active_node_id | shape.present.gate |
