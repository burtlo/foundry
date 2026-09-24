# build

Status: **draft capability spec**

The `foundry build` command group runs repository-configured verification and validates build-phase exit criteria. Manifest verification commands come from `.foundry/app.yaml` `verification`. Who performs builder commits is unresolved; see [gaps.md](gaps.md). Hub: [cli.md](cli.md).

---

## build

### Purpose

Execute the next ready work item from the execution graph (or a specified item): delegate to the configured builder, stage changes, and create an intermediate accountability commit on `feature_branch` when the item completes. Does not seal the `execute.build` visit. [v1-spec.md](../v1-spec.md#executebuild) assigns that commit to `visit transition` instead. Both descriptions are draft; [gaps.md](gaps.md) records the conflict.

### Who invokes

| Actor | When |
|---|---|
| steward | Execute phase agent traffic-cop at `execute.build` |
| engine | When steward capability `build.build` is authorized |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--work-item` | no | Specific graph work item id (default: next ready) |
| `--summary` | no | Short summary for commit message template |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry build build --run run-2026-09-24-porcelain-003 --work-item implement-core --summary "Add harness retrieval stage" --json
```

### Sample JSON / exit code

Exit `0` when work item completes and commit is recorded. Exit `1` on build failure or blocked graph.

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "work_item_id": "implement-core",
  "status": "completed",
  "commit_sha": "4f91c2a8b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6",
  "receipt_id": "rcpt-build-004"
}
```

### Used by factory-flow checks / nodes

| Node / check | Role |
|---|---|
| `execute.build` | Primary build step; graph traffic-cop |
| `validate-build-exit` | `on_seal` after all items complete |
| `prior-execute-build-sealed` | Prerequisite for `execute.test` |

### Cross-links

- [cli-build.md](cli-build.md) — `test`, `validate-exit`, `commit finalize`
- [cli-graph.md](cli-graph.md) — graph readiness
- [cli-receipt.md](cli-receipt.md) — work item receipts

---

## test

### Purpose

Run repo-configured verification commands from the manifest (`verification.commands`) after the build graph completes. Supports repair loop routing from `execute.test.gate` and `verify.code_quality.gate`.

### Who invokes

| Actor | When |
|---|---|
| steward | `execute.test` step (repairer on failure) |
| engine | Machine gate evaluation at `execute.test.gate` |
| eval | Harness verification fixtures |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--suite` | no | Subset id from manifest (default: all required) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry build test --run run-2026-09-24-porcelain-003 --json
```

### Sample JSON / exit code

Exit `0` when all required commands pass. Exit `1` on failure.

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "passed": true,
  "results": [
    {"id": "unit", "argv": ["make", "test"], "exit_code": 0, "duration_ms": 12450}
  ]
}
```

### Used by factory-flow checks / nodes

| Node / check | Role |
|---|---|
| `execute.test` | Run verification after build |
| `execute.test.gate` | Routes to `execute.commit` or repair (`execute.build`) |
| `prior-execute-test-sealed` | Prerequisite for `execute.commit` |
| `verify.code_quality` | Optional deeper review when `review-enabled` |

### Cross-links

- [cli-app.md](cli-app.md) — verification config in manifest
- [cli-visit.md](cli-visit.md) — `transition` to close test visit
- [v1-spec.md](../v1-spec.md#executetest) — repair loop semantics

---

## validate-exit

### Purpose

Verify all execution graph work items are completed, delegation is proven in the ledger, and required receipts exist before `execute.build` may seal. Catalog probe: `validate-build-exit` (`command: validate_build_exit`).

### Who invokes

| Actor | When |
|---|---|
| engine | `execute.build` `on_seal` → `validate-build-exit` |
| steward | Build traffic-cop before requesting `visit transition` |
| eval | Harness build completeness assertions |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--evidence` | no | Path to orchestrator step receipt JSON |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry build validate-exit --run run-2026-09-24-porcelain-003 --json
```

### Sample JSON / exit code

Check probe: exit `0` = pass, `1` = fail.

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "graph_id": "eg-2026-09-24-003",
  "all_complete": true,
  "work_items": [
    {"id": "implement-core", "status": "completed", "receipt_id": "rcpt-build-004", "commit_sha": "4f91c2a..."}
  ],
  "open_launches": 0
}
```

Failure (exit `1`):

```json
{
  "all_complete": false,
  "incomplete": ["implement-tests"],
  "reason": "BUILD_GRAPH_INCOMPLETE"
}
```

### Used by factory-flow checks / nodes

| Node / check | Hook | Role |
|---|---|---|
| `validate-build-exit` | catalog `command: validate_build_exit` | Probe body |
| `execute.build` | `on_seal` → `validate-build-exit` | Blocks seal until graph complete |
| `agent-receipt-sealed` | `execute.build` `on_seal` | Receipt evidence |

### Cross-links

- [cli-check.md](cli-check.md) — `check eval --check validate-build-exit`
- [cli-graph.md](cli-graph.md) — graph file and id
- [cli-ledger.md](cli-ledger.md) — delegation event queries

---

## commit finalize

### Purpose

Create the **final summarizing commit** at `execute.commit` (may be empty/no-op). Records `final_commit_sha` in state and publishes the `final-commit` reference artifact (`kind: reference`, `scheme: git_commit`) per [artifacts.md](../workflow-schema-v1/artifacts.md#publishing).

### Who invokes

| Actor | When |
|---|---|
| steward | Commit agent subagent at `execute.commit` |
| engine | Enforces `final-commit-recorded` before verify intake |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--message` | yes | Summarizing commit message (may trigger empty commit) |
| `--allow-empty` | no | Permit empty commit when tree unchanged (default: true) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry build commit finalize --run run-2026-09-24-porcelain-003 --message "feat(harness): retrieval stage and tests" --json
```

### Sample JSON / exit code

Exit `0` on success.

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "feature_branch": "lynn/porcelain-003",
  "commit_sha": "9e8d7c6b5a493827160514131211100908070605",
  "empty": false,
  "artifact": {
    "id": "final-commit",
    "uri": "git:commit/9e8d7c6b5a493827160514131211100908070605"
  },
  "state_patched": {"final_commit_sha": "9e8d7c6b5a493827160514131211100908070605"}
}
```

### Used by factory-flow checks / nodes

| Node / check | Hook | Role |
|---|---|---|
| `execute.commit` | step | Dedicated final commit agent |
| `final-commit-recorded` | `execute.commit` `on_seal`, `execute.commit.gate`, `verify.intake` | State and artifact required |
| `verify.intake` | reads `execute.commit.final-commit` artifact | Whole-branch review baseline |
| `prior-execute-commit-sealed` | verify intake `on_examine` | Execute phase complete |

### Cross-links

- [cli-artifact.md](cli-artifact.md) — `artifact publish` for `final-commit`
- [cli-branch.md](cli-branch.md) — commits on feature branch
- [v1-spec.md](../v1-spec.md#executecommit) — never amend prior builder commits

---

For CLI mechanics borrowed from earlier prototypes, see [cli-poc-transition.md](cli-poc-transition.md).
