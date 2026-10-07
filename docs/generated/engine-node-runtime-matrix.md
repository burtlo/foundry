# Engine node runtime matrix

Flow: `implementation`. Generated inventory for [implementation-flow-runtime.md](../features/implementation-flow-runtime.md) (see archived [engine DSL plan](../plans/archive/engine-dsl-orchestration-plan.md)).

Regenerate: `just engine-matrix` (or `foundry dev engine-matrix`).

| node_id | kind | decider | hooks (checks) | allow.cli | task.yaml | operations.yaml | ops in node.yaml | python complete | advance_classifier | gate resolver | boundary_status |
|---|---|---|---|---|:---:|:---:|:---:|:---:|---|---|---|
| shape.intake | step | — | validate-manifest, intake-receipt-sealed, agent-receipt-sealed | visit.intake.complete, visit.state_patch | no | yes | yes | run_shape_intake_complete | classify:host_step, host_advance, host_boundary_wait | — | implemented |
| shape.examine | step | — | prior-shape-intake-sealed, agent-receipt-sealed | run.agent.submit, visit.examine.complete | yes | yes | yes | run_shape_examine_complete | classify:task_bound_step, task_bound_advance, task_bound_boundary_wait | — | implemented |
| shape.examine.gate | gate | user | prior-examine-sealed | — | no | no | no | — | classify:user_gate | — | gate-user |
| shape.present | step | — | prior-examine-sealed, agent-receipt-sealed | run.agent.submit, visit.present.complete | yes | no | no | run_shape_present_complete | classify:task_bound_step, task_bound_advance, task_bound_boundary_wait | — | implemented |
| shape.present.gate | gate | user | prior-present-sealed | — | no | no | no | — | classify:user_gate | — | gate-user |
| shape.record | step | — | prior-present-sealed, approved-ac-recorded, agent-receipt-sealed | run.agent.submit, visit.record.complete | yes | no | no | run_shape_record_complete | classify:task_bound_step, task_bound_advance, task_bound_boundary_wait | — | implemented |
| shape.record.gate | gate | user | prior-shape-record-sealed, approved-ac-recorded | — | no | no | no | — | classify:user_gate | — | gate-user |
| execute.start | gate | user | prior-shape-record-sealed, approved-ac-recorded | — | no | no | no | — | classify:user_gate | — | gate-user |
| execute.intake | step | — | approved-ac-recorded, prior-shape-record-sealed, validate-manifest, validate-git-clean-execute, intake-receipt-sealed, agent-receipt-sealed | — | no | yes | yes | run_execute_intake_complete | classify:host_step, host_advance | — | implemented |
| execute.intake.gate | gate | engine | prior-execute-intake-sealed, intake-receipt-sealed | — | no | no | no | — | classify:engine_gate | `registry:nodes/execute.intake.gate/gate.rules.yaml` | gate-engine |
| execute.branch | step | — | prior-execute-intake-sealed | — | no | yes | yes | run_execute_branch_complete | classify:git_mechanical_step, git_mechanical_advance | — | implemented |
| execute.plan | step | — | feature-branch-set, ensure-execution-graph-reference, execution-graph-set, agent-receipt-sealed | run.agent.submit, visit.plan.complete | yes | yes | yes | run_execute_plan_complete | classify:task_bound_step, task_bound_advance, task_bound_boundary_wait | — | implemented |
| execute.build | step | — | execution-graph-set, feature-branch-set, validate-build-exit, agent-receipt-sealed | — | no | yes | yes | run_execute_build_complete | classify:host_step, host_advance | — | implemented |
| execute.test | step | — | prior-execute-build-sealed, agent-receipt-sealed | — | no | yes | yes | run_execute_test_complete | classify:host_step, host_advance | — | implemented |
| execute.test.gate | gate | engine | prior-execute-test-sealed | — | no | no | no | — | classify:engine_gate | `registry:nodes/execute.test.gate/gate.rules.yaml` | gate-engine |
| execute.repair.limit.gate | gate | engine | repair-within-limit | — | no | no | no | — | classify:engine_gate | `registry:nodes/execute.repair.limit.gate/gate.rules.yaml` | gate-engine |
| execute.commit | step | — | prior-execute-test-sealed, final-commit-recorded, agent-receipt-sealed | — | no | yes | yes | run_execute_commit_complete | classify:host_step, host_advance | — | implemented |
| execute.commit.gate | gate | engine | reverify-within-limit, prior-execute-commit-sealed, final-commit-recorded | — | no | no | no | — | classify:engine_gate | `registry:nodes/execute.commit.gate/gate.rules.yaml` | gate-engine |
| verify.intake | step | — | prior-execute-commit-sealed, feature-branch-set, final-commit-recorded, validate-manifest, validate-verify-context, intake-receipt-sealed, agent-receipt-sealed | — | no | yes | yes | run_verify_intake_complete | classify:host_step, host_advance | — | implemented |
| verify.intake.gate | gate | engine | prior-verify-intake-sealed, intake-receipt-sealed | — | no | no | no | — | classify:engine_gate | `registry:nodes/verify.intake.gate/gate.rules.yaml` | gate-engine |
| verify.acceptance | step | — | prior-verify-intake-sealed, agent-receipt-sealed | run.agent.submit | yes | yes | yes | run_verify_acceptance_complete | classify:task_bound_step, task_bound_advance, task_bound_boundary_wait | — | implemented |
| verify.acceptance.gate | gate | engine | prior-verify-acceptance-sealed | — | no | no | no | — | classify:engine_gate | `registry:nodes/verify.acceptance.gate/gate.rules.yaml` | gate-engine |
| verify.code_quality | step | — | prior-verify-acceptance-sealed, review-enabled, agent-receipt-sealed | — | no | yes | yes | run_verify_code_quality_complete | classify:host_step, host_advance | — | implemented |
| verify.code_quality.gate | gate | engine | code-quality-done-or-skipped | — | no | no | no | — | classify:engine_gate | `registry:nodes/verify.code_quality.gate/gate.rules.yaml` | gate-engine |
| verify.code_review | step | — | acceptance-passed, code-quality-done-or-skipped | — | no | yes | yes | run_verify_code_review_complete | classify:host_step, host_advance | — | implemented |
| verify.code_review.gate | gate | user | prior-verify-acceptance-sealed | — | no | no | no | — | classify:user_gate | — | gate-user |
| verify.complete | step | — | code-review-approved | — | no | yes | yes | run_verify_complete_complete | classify:host_step, host_advance | — | implemented |
| verify.complete.gate | gate | user | — | — | no | no | no | — | classify:user_gate | — | gate-user |
| deliver.stub | step | — | — | — | no | yes | yes | run_deliver_stub_complete | classify:host_step, host_advance | — | implemented |

Warnings:

- python-only node without bound operations: shape.present (run_shape_present_complete)
- python-only node without bound operations: shape.record (run_shape_record_complete)
