# git

Status: **draft capability spec**

The `foundry git` command group performs read-only git workspace probes against `workspace:` roots defined in [capabilities.md](../workflow-schema-v1/capabilities.md#paths). Commands never commit, branch, or mutate the repository; mutating git operations live under [cli-branch.md](cli-branch.md) and [cli-build.md](cli-build.md). Clean-tree semantics follow [v1-spec.md](../v1-spec.md#git-cleanliness). Hub: [cli.md](cli.md).

---

## default-branch

### Purpose

Detect the repository default branch name (`main`, `master`, or remote HEAD). Populates `state.default_branch` during `execute.branch` and supplies diff baseline for `verify.intake`.

### Who invokes

| Actor | When |
|---|---|
| steward | `execute.branch` step instructions |
| engine | Verify diff scope resolution |
| operator | Debug branch baseline |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--workspace` | no | Application repo root (default: cwd) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry git default-branch --workspace workspace:. --json
```

### Sample JSON / exit code

Exit `0` on success. Exit `1` when not a git repository or default branch cannot be resolved.

```json
{
  "workspace": "workspace:.",
  "default_branch": "main",
  "resolved_from": "remote.origin.head"
}
```

### Used by factory-flow checks / nodes

| Node / check | Role |
|---|---|
| `execute.branch` | Reads `config.git`; writes `default_branch` to state |
| `verify.intake` | Whole-branch diff vs `default_branch` per [v1-spec.md](../v1-spec.md#verifyintake) |

### Cross-links

- [cli-branch.md](cli-branch.md) — `create` uses default branch as start point
- [cli-git.md](cli-git.md) — `clean-check`

---

## clean-check

### Purpose

Verify the workspace git tree is **clean** per v1: no uncommitted changes to **tracked** files and no **untracked** files present. Read-only probe for execute intake; shape intake does not require a clean tree.

### Who invokes

| Actor | When |
|---|---|
| engine | `validate-git-clean-execute` catalog check at `execute.intake` `on_open` |
| steward | Execute intake worker; results sealed in intake receipt |
| operator | Pre-flight before `/craft-execute` |
| eval | Harness git fixture assertions |

### Flags

| Flag | Required | Description |
|---|---|---|
| `--workspace` | no | Application repo root (default: cwd) |
| `--json` | no | Emit machine-readable result |

### Sample invocation

```text
foundry git clean-check --workspace workspace:. --json
```

### Sample JSON / exit code

Check probe mapping: exit `0` = pass (clean), `1` = fail (dirty), `2` = not_applicable.

Clean tree (exit `0`):

```json
{
  "clean": true,
  "tracked_dirty": [],
  "untracked": []
}
```

Dirty tree (exit `1`):

```json
{
  "clean": false,
  "tracked_dirty": ["internal/harness/stage.go"],
  "untracked": ["tmp-scratch.txt"]
}
```

### Used by factory-flow checks / nodes

| Node / check | Hook | Role |
|---|---|---|
| `validate-git-clean-execute` | catalog `command: validate_git_clean_execute` | Probe body |
| `execute.intake` | `on_open` → `validate-git-clean-execute` | Execute phase requires clean tree |
| `execute.intake.gate` | `on_examine` → `intake-receipt-sealed` | Intake receipt must record pass/fail |

### Cross-links

- [cli-check.md](cli-check.md) — `check eval --check validate-git-clean-execute`
- [v1-spec.md](../v1-spec.md#git-cleanliness) — clean definition and phase rules
- [cli-app.md](cli-app.md) — manifest valid before execute intake

---

For CLI mechanics borrowed from earlier prototypes, see [cli-poc-transition.md](cli-poc-transition.md).
