# branch

Status: **draft capability spec**

The `foundry branch` command group names and creates the per-run feature branch in the application repository. Branch identity is run state (`feature_branch`, `feature_branch_head`) per [run-record.md](../workflow-schema-v1/run-record.md) and [capabilities.md](../workflow-schema-v1/capabilities.md) `allow.state`; execute and verify nodes consume it in [factory-flow.yaml](../../.cursor/foundry/flows/factory-flow.yaml). Git mutations are engine- or steward-invoked CLI operations; builders do not run git directly per [v1-spec.md](../v1-spec.md#executebuild). Hub: [cli.md](cli.md).

---

## name

### Purpose

Render the feature branch name from the manifest `git.branch_pattern` and run context (`run_slug`, `developer_first_name`, optional `issue_key`). Does not touch the repository.

### Who invokes

| Actor | When |
|---|---|
| steward | `execute.branch` before `branch create` |
| operator | Preview branch name for a run |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id (*default: current run in cwd) |
| `--pattern` | no | Override manifest pattern |
| `--developer` | no | Developer first name (default: from run state) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry branch name --run run-2026-09-24-porcelain-003 --json
```

### Sample JSON / exit code

Exit `0` on success.

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "branch_name": "lynn/porcelain-003",
  "pattern": "{developer}/{run_slug}"
}
```

### Used by factory-flow checks / nodes

| Node / check | Role |
|---|---|
| `execute.branch` | Supplies name passed to `branch create` |
| `feature-branch-set` | Expression check after branch recorded in state |

### Cross-links

- [cli-branch.md](cli-branch.md) — `create`
- [cli-git.md](cli-git.md) — `default-branch` for start point
- [cli-run.md](cli-run.md) — `run_slug` in run state

---

## create

### Purpose

Create and checkout the feature branch from the default branch (or `--start-point`). Records `feature_branch` and initial `feature_branch_head` in run state.

### Who invokes

| Actor | When |
|---|---|
| steward | `execute.branch` step (execute phase agent) |
| engine | May invoke on steward behalf when capability allows |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--run` | yes* | Run id |
| `--workspace` | no | Application repo root (default: cwd) |
| `--name` | yes | Branch name (typically from `branch name`) |
| `--start-point` | no | Ref to branch from (default: detected default branch) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry branch create --run run-2026-09-24-porcelain-003 --name lynn/porcelain-003 --json
```

### Sample JSON / exit code

Exit `0` on success. Exit `1` if branch exists, checkout fails, or tree is not clean when required.

```json
{
  "run_id": "run-2026-09-24-porcelain-003",
  "feature_branch": "lynn/porcelain-003",
  "start_point": "main",
  "head_sha": "a1b2c3d4e5f6789012345678abcdef9012345678",
  "created": true
}
```

### Used by factory-flow checks / nodes

| Node / check | Hook | Role |
|---|---|---|
| `execute.branch` | step | Creates feature branch after `execute.intake` seals |
| `prior-execute-intake-sealed` | `execute.branch` `on_examine` | Prerequisite |
| `feature-branch-set` | `execute.plan`, `execute.build`, `verify.intake` | State must include branch |
| `execute.plan` → `execute.build` | connection | Build runs on feature branch |

### Cross-links

- [cli-git.md](cli-git.md) — `default-branch`, `clean-check` (intake prerequisite)
- [cli-build.md](cli-build.md) — commits on `feature_branch`
- [cli-graph.md](cli-graph.md) — planner runs after branch exists

---

For CLI mechanics borrowed from earlier prototypes, see [cli-poc-transition.md](cli-poc-transition.md).
