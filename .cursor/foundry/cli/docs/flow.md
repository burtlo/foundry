# Flow: `implementation`

Generated from `.cursor/foundry/flows/factory-flow.yaml`. Regenerate with `foundry doc build` or `foundry dev docs`.

Registry version: `2`
Entry node: `shape.intake`
Source: [factory-flow.yaml](../../flows/factory-flow.yaml)

## Graph

```mermaid
flowchart TD

  deliver_stub["deliver.stub"]
  execute_branch["execute.branch"]
  execute_build["execute.build"]
  execute_commit["execute.commit"]
  execute_commit_gate["execute.commit.gate"]
  execute_intake["execute.intake"]
  execute_intake_gate["execute.intake.gate"]
  execute_plan["execute.plan"]
  execute_repair_limit_gate["execute.repair.limit.gate"]
  execute_start["execute.start"]
  execute_test["execute.test"]
  execute_test_gate["execute.test.gate"]
  shape_examine["shape.examine"]
  shape_examine_gate["shape.examine.gate"]
  shape_intake["shape.intake"]
  shape_present["shape.present"]
  shape_present_gate["shape.present.gate"]
  shape_record["shape.record"]
  shape_record_gate["shape.record.gate"]
  verify_acceptance["verify.acceptance"]
  verify_acceptance_gate["verify.acceptance.gate"]
  verify_code_quality["verify.code_quality"]
  verify_code_quality_gate["verify.code_quality.gate"]
  verify_code_review["verify.code_review"]
  verify_code_review_gate["verify.code_review.gate"]
  verify_complete["verify.complete"]
  verify_complete_gate["verify.complete.gate"]
  verify_intake["verify.intake"]
  verify_intake_gate["verify.intake.gate"]

  shape_intake --> shape_examine
  shape_examine --> shape_present
  shape_examine --> shape_examine_gate
  shape_present --> shape_present_gate
  shape_record --> shape_record_gate
  execute_intake --> execute_intake_gate
  execute_branch --> execute_plan
  execute_plan --> execute_build
  execute_build --> execute_test
  execute_test --> execute_test_gate
  execute_commit --> execute_commit_gate
  verify_intake --> verify_intake_gate
  verify_code_quality --> verify_code_quality_gate
  verify_code_quality --> verify_code_review
  verify_code_review --> verify_code_review_gate
  verify_complete --> verify_complete_gate
  shape_examine_gate --> shape_present:|accept|
  shape_examine_gate --> shape_examine:|reject|
  shape_present_gate --> shape_examine:|reject|
  shape_present_gate --> shape_record:|accept|
  shape_record_gate --> execute_start:|accept|
  shape_record_gate --> shape_present:|hold loop:reshape_plan|
  execute_start --> execute_intake:|accept|
  execute_intake_gate --> execute_branch:|pass|
  execute_test_gate --> execute_commit:|pass|
  execute_test_gate --> execute_repair_limit_gate:|repair|
  execute_repair_limit_gate --> execute_build:|proceed loop:repair|
  execute_commit_gate --> verify_intake:|pass|
  verify_intake_gate --> verify_acceptance:|pass|
  verify_code_quality_gate --> verify_code_review:|pass|
  verify_code_quality_gate --> execute_repair_limit_gate:|repair|
  verify_code_review_gate --> verify_complete:|accept|
  verify_code_review_gate --> shape_intake:|reshape loop:reshape|
  verify_code_review_gate --> execute_repair_limit_gate:|reject|
  verify_complete_gate --> deliver_stub:|accept|
  verify_acceptance --> verify_acceptance_gate
  verify_acceptance_gate --> verify_code_quality:|pass|
  verify_acceptance_gate --> execute_plan:|replan loop:reexecute|
  verify_acceptance_gate --> shape_intake:|reshape loop:reshape|
  verify_acceptance_gate --> execute_intake:|rework_execute loop:reexecute|
```

## Concepts

Graph routing rules: [graph.md](concepts/graph.md). Check catalog semantics: [control-plane.md](concepts/control-plane.md).

## Nodes

| Node | Kind | Title | Doc |
|---|---|---|---|
| `deliver.stub` | `step` | Deliver phase stub (terminal) | [doc](nodes/deliver.stub.md) |
| `execute.branch` | `step` | Create the feature branch | [doc](nodes/execute.branch.md) |
| `execute.build` | `step` | Build graph work items — builders commit via CLI | [doc](nodes/execute.build.md) |
| `execute.commit` | `step` | Final summarizing commit on feature branch | [doc](nodes/execute.commit.md) |
| `execute.commit.gate` | `gate` | Execute commit recorded | [doc](nodes/execute.commit.gate.md) |
| `execute.intake` | `step` | Execute intake — plan alignment and clean git tree | [doc](nodes/execute.intake.md) |
| `execute.intake.gate` | `gate` | Execute intake blocked check | [doc](nodes/execute.intake.gate.md) |
| `execute.plan` | `step` | Execution graph and phase-scoped internal brief | [doc](nodes/execute.plan.md) |
| `execute.repair.limit.gate` | `gate` | Repair loop guard — count prior repair cycles before build | [doc](nodes/execute.repair.limit.gate.md) |
| `execute.start` | `gate` | Start execute phase | [doc](nodes/execute.start.md) |
| `execute.test` | `step` | Run repo verification and repair loop | [doc](nodes/execute.test.md) |
| `execute.test.gate` | `gate` | Execute test pass | [doc](nodes/execute.test.gate.md) |
| `shape.examine` | `step` | Shape examination — draft AC and clarifying questions | [doc](nodes/shape.examine.md) |
| `shape.examine.gate` | `gate` | Open questions remain — present anyway or continue examination | [doc](nodes/shape.examine.gate.md) |
| `shape.intake` | `step` | Shape intake — validate app manifest and capture work request | [doc](nodes/shape.intake.md) |
| `shape.present` | `step` | Shape present — succinct plan and AC presentation | [doc](nodes/shape.present.md) |
| `shape.present.gate` | `gate` | Plan presentation — refine or record acceptance criteria | [doc](nodes/shape.present.gate.md) |
| `shape.record` | `step` | Shape record — freeze approved_ac and living plan | [doc](nodes/shape.record.md) |
| `shape.record.gate` | `gate` | Record acceptance criteria | [doc](nodes/shape.record.gate.md) |
| `verify.acceptance` | `step` | Automated acceptance criteria validation | [doc](nodes/verify.acceptance.md) |
| `verify.acceptance.gate` | `gate` | Acceptance result routing | [doc](nodes/verify.acceptance.gate.md) |
| `verify.code_quality` | `step` | Automated lint, Bugbot, and security review | [doc](nodes/verify.code_quality.md) |
| `verify.code_quality.gate` | `gate` | Code quality result routing | [doc](nodes/verify.code_quality.gate.md) |
| `verify.code_review` | `step` | Human code review — single turn | [doc](nodes/verify.code_review.md) |
| `verify.code_review.gate` | `gate` | Human code review decision | [doc](nodes/verify.code_review.gate.md) |
| `verify.complete` | `step` | Verify phase complete | [doc](nodes/verify.complete.md) |
| `verify.complete.gate` | `gate` | Verify complete | [doc](nodes/verify.complete.gate.md) |
| `verify.intake` | `step` | Verify intake — branch diff, receipts, and plan alignment | [doc](nodes/verify.intake.md) |
| `verify.intake.gate` | `gate` | Verify intake blocked check | [doc](nodes/verify.intake.gate.md) |

## Connections

| Id | From | To | Routing |
|---|---|---|---|
| `shape.intake-to-shape.examine` | `shape.intake` | `shape.examine` | outcomes=['completed'] |
| `shape.examine-to-shape.present` | `shape.examine` | `shape.present` | outcomes=['completed']; when=state.open_clarifying_questions_count == 0 |
| `shape.examine-to-shape.examine.gate` | `shape.examine` | `shape.examine.gate` | outcomes=['completed']; when=state.open_clarifying_questions_count != 0 |
| `shape.present-to-shape.present.gate` | `shape.present` | `shape.present.gate` | outcomes=['completed'] |
| `shape.record-to-shape.record.gate` | `shape.record` | `shape.record.gate` | outcomes=['completed'] |
| `execute.intake-to-execute.intake.gate` | `execute.intake` | `execute.intake.gate` | outcomes=['completed'] |
| `execute.branch-to-execute.plan` | `execute.branch` | `execute.plan` | outcomes=['completed'] |
| `execute.plan-to-execute.build` | `execute.plan` | `execute.build` | outcomes=['completed'] |
| `execute.build-to-execute.test` | `execute.build` | `execute.test` | outcomes=['completed'] |
| `execute.test-to-execute.test.gate` | `execute.test` | `execute.test.gate` | outcomes=['completed'] |
| `execute.commit-to-execute.commit.gate` | `execute.commit` | `execute.commit.gate` | outcomes=['completed'] |
| `verify.intake-to-verify.intake.gate` | `verify.intake` | `verify.intake.gate` | outcomes=['completed'] |
| `verify.code_quality-to-verify.code_quality.gate` | `verify.code_quality` | `verify.code_quality.gate` | outcomes=['completed'] |
| `verify.code_quality-to-verify.code_review-skipped` | `verify.code_quality` | `verify.code_review` | outcomes=['not_applicable'] |
| `verify.code_review-to-verify.code_review.gate` | `verify.code_review` | `verify.code_review.gate` | outcomes=['completed'] |
| `verify.complete-to-verify.complete.gate` | `verify.complete` | `verify.complete.gate` | outcomes=['completed'] |
| `shape.examine.gate-to-shape.present-present` | `shape.examine.gate` | `shape.present` | outcomes=['completed']; decisions=['accept'] |
| `shape.examine.gate-to-shape.examine-continue` | `shape.examine.gate` | `shape.examine` | outcomes=['completed']; decisions=['reject'] |
| `shape.present.gate-to-shape.examine-refine` | `shape.present.gate` | `shape.examine` | outcomes=['completed']; decisions=['reject'] |
| `shape.present.gate-to-shape.record-record` | `shape.present.gate` | `shape.record` | outcomes=['completed']; decisions=['accept'] |
| `shape.record.gate-to-execute.start-record` | `shape.record.gate` | `execute.start` | outcomes=['completed']; decisions=['accept'] |
| `shape.record.gate-to-shape.present-reshape_plan` | `shape.record.gate` | `shape.present` | outcomes=['completed']; decisions=['hold']; loop=reshape_plan |
| `execute.start-to-execute.intake-start` | `execute.start` | `execute.intake` | outcomes=['completed']; decisions=['accept'] |
| `execute.intake.gate-to-execute.branch-pass` | `execute.intake.gate` | `execute.branch` | outcomes=['completed']; decisions=['pass'] |
| `execute.test.gate-to-execute.commit-pass` | `execute.test.gate` | `execute.commit` | outcomes=['completed']; decisions=['pass'] |
| `execute.test.gate-to-execute.repair.limit.gate-repair` | `execute.test.gate` | `execute.repair.limit.gate` | outcomes=['completed']; decisions=['repair'] |
| `execute.repair.limit.gate-to-execute.build-proceed` | `execute.repair.limit.gate` | `execute.build` | outcomes=['completed']; decisions=['proceed']; loop=repair |
| `execute.commit.gate-to-verify.intake-pass` | `execute.commit.gate` | `verify.intake` | outcomes=['completed']; decisions=['pass'] |
| `verify.intake.gate-to-verify.acceptance-pass` | `verify.intake.gate` | `verify.acceptance` | outcomes=['completed']; decisions=['pass'] |
| `verify.code_quality.gate-to-verify.code_review-pass` | `verify.code_quality.gate` | `verify.code_review` | outcomes=['completed']; decisions=['pass'] |
| `verify.code_quality.gate-to-execute.repair.limit.gate-repair` | `verify.code_quality.gate` | `execute.repair.limit.gate` | outcomes=['completed']; decisions=['repair'] |
| `verify.code_review.gate-to-verify.complete-approve` | `verify.code_review.gate` | `verify.complete` | outcomes=['completed']; decisions=['accept'] |
| `verify.code_review.gate-to-shape.intake-reshape` | `verify.code_review.gate` | `shape.intake` | outcomes=['completed']; decisions=['reshape']; loop=reshape |
| `verify.code_review.gate-to-execute.repair.limit.gate-repair` | `verify.code_review.gate` | `execute.repair.limit.gate` | outcomes=['completed']; decisions=['reject'] |
| `verify.complete.gate-to-deliver.stub-complete` | `verify.complete.gate` | `deliver.stub` | outcomes=['completed']; decisions=['accept'] |
| `verify.acceptance-to-verify.acceptance.gate` | `verify.acceptance` | `verify.acceptance.gate` | outcomes=['completed'] |
| `verify.acceptance.gate-to-verify.code_quality-pass` | `verify.acceptance.gate` | `verify.code_quality` | outcomes=['completed']; decisions=['pass'] |
| `verify.acceptance.gate-to-execute.plan-replan` | `verify.acceptance.gate` | `execute.plan` | outcomes=['completed']; decisions=['replan']; loop=reexecute |
| `verify.acceptance.gate-to-shape.intake-reshape` | `verify.acceptance.gate` | `shape.intake` | outcomes=['completed']; decisions=['reshape']; loop=reshape |
| `verify.acceptance.gate-to-execute.intake-rework_execute` | `verify.acceptance.gate` | `execute.intake` | outcomes=['completed']; decisions=['rework_execute']; loop=reexecute |

## Check catalog

| Check id | Definition |
|---|---|
| `acceptance-passed` | when: `history.last('gate.resolved', node_id='verify.acceptance.gate') != null && history.last('gate.resolved', node_id='verify.acceptance.gate').decision == 'pass'` |
| `agent-receipt-sealed` | when: `history.count('receipt.linked', visit_id=visit.id, schema='registry:schemas/agent-receipt.schema.json') >= 1` |
| `approved-ac-recorded` | when: `state.approved_ac_version >= 1` |
| `code-quality-done-or-skipped` | when: `!config.review.enabled || (history.last('visit.sealed', node_id='verify.code_quality') != null && history.last('visit.sealed', node_id='verify.code_quality').outcome in ['completed', 'not_applicable'])` |
| `code-review-approved` | when: `history.last('gate.resolved', node_id='verify.code_review.gate') != null && history.last('gate.resolved', node_id='verify.code_review.gate').decision == 'accept'` |
| `ensure-execution-graph-reference` | command: `ensure_execution_graph_reference` |
| `execution-graph-set` | when: `state.execution_graph_id != null` |
| `feature-branch-set` | when: `state.feature_branch != null` |
| `final-commit-recorded` | when: `state.final_commit_sha != null` |
| `intake-receipt-sealed` | when: `history.count('receipt.linked', visit_id=visit.id, schema='registry:schemas/intake-receipt.schema.json') >= 1` |
| `prior-examine-sealed` | when: `history.last('visit.sealed', node_id='shape.examine') != null && history.last('visit.sealed', node_id='shape.examine').outcome == 'completed'` |
| `prior-execute-build-sealed` | when: `history.last('visit.sealed', node_id='execute.build') != null && history.last('visit.sealed', node_id='execute.build').outcome == 'completed'` |
| `prior-execute-commit-sealed` | when: `history.last('visit.sealed', node_id='execute.commit') != null && history.last('visit.sealed', node_id='execute.commit').outcome == 'completed'` |
| `prior-execute-intake-sealed` | when: `history.last('visit.sealed', node_id='execute.intake') != null && history.last('visit.sealed', node_id='execute.intake').outcome == 'completed'` |
| `prior-execute-test-sealed` | when: `history.last('visit.sealed', node_id='execute.test') != null && history.last('visit.sealed', node_id='execute.test').outcome == 'completed'` |
| `prior-present-sealed` | when: `history.last('visit.sealed', node_id='shape.present') != null && history.last('visit.sealed', node_id='shape.present').outcome == 'completed'` |
| `prior-shape-intake-sealed` | when: `history.last('visit.sealed', node_id='shape.intake') != null && history.last('visit.sealed', node_id='shape.intake').outcome == 'completed'` |
| `prior-shape-record-sealed` | when: `history.last('visit.sealed', node_id='shape.record') != null && history.last('visit.sealed', node_id='shape.record').outcome == 'completed'` |
| `prior-verify-acceptance-sealed` | when: `history.last('visit.sealed', node_id='verify.acceptance') != null && history.last('visit.sealed', node_id='verify.acceptance').outcome == 'completed'` |
| `prior-verify-intake-sealed` | when: `history.last('visit.sealed', node_id='verify.intake') != null && history.last('visit.sealed', node_id='verify.intake').outcome == 'completed'` |
| `repair-within-limit` | when: `history.count('connection.taken', loop='repair') <= config.limits.repair` |
| `reverify-within-limit` | when: `history.count('visit.sealed', node_id='verify.intake') <= config.limits.reverify` |
| `review-enabled` | when: `config.review.enabled` |
| `validate-build-exit` | command: `validate_build_exit` |
| `validate-git-clean-execute` | command: `validate_git_clean_execute` |
| `validate-manifest` | command: `validate_manifest` |
| `validate-verify-context` | command: `validate_verify_context` |
