---
name: factory-bootstrap
description: >-
  Shared prerequisite for factory skills that need team variables without a
  parent orchestrator. Resolves factory_root and app_folder, then loads
  role-scoped FactoryConfig via foundry.py config get. Library skill — consumed
  by build-with-tests and future factory skills; not a user-facing workflow.
disable-model-invocation: true
---

# Factory bootstrap

**Library skill.** Other skills **Read and follow this file** when they need team profile settings without a parent passing `FactoryConfig`. Do not hand-parse `.cursor/foundry/profiles/*.yaml`.

Orchestrators (`foundry`, `bug-squash`) may inline the same steps or delegate here — they already load config at kickoff.

---

## Inputs (set by the consuming skill)

| Input | Required | Description |
|-------|----------|-------------|
| `{bootstrap_role}` | Yes | CLI role for `config get` — must exist in [factory-config-packet.md](../../foundry/templates/factory-config-packet.md) and `foundry_mechanics.py` `ROLE_KEYS` |
| `FactoryConfig` in prompt | No | When present, **skip** bootstrap and use that JSON |
| `{app_folder}` hint | No | When the consuming skill already resolved the app (e.g. from a ticket), pass it in — skip app resolution steps 1–2 |

Common `{bootstrap_role}` values:

| Consumer | Role |
|----------|------|
| `build-with-tests` | `build-with-tests` |
| `/ticket-workflow`, `/branch-to-jira-task` | `ticket-workflow` (see [command-bootstrap.md](../../foundry/templates/command-bootstrap.md)) |
| `/documentation-workflow` | `documentation-workflow` |
| Future implementer skill | `feature-builder`, `backend-builder`, or `client-builder` |
| Future read-only skill | `codebase-researcher`, `implementation-validator` |
| Full settings (Jira, workspace list) | `parent` |

Role slices and example JSON: [factory-config-packet.md](../../foundry/templates/factory-config-packet.md).

---

## Procedure

### 0. Use existing FactoryConfig when provided

If the launch prompt includes **FactoryConfig** JSON (any role that satisfies the consumer’s needs), use it. Template paths are already resolved. **Do not** call `config get` again unless `{app_folder}` changed.

Acceptable parent roles for template-only consumers: `build-with-tests`, `backend-builder`, `client-builder`, `feature-builder` (all include `templates.implement` / `add_tests` / `run_tests` when applicable).

### 1. Resolve `{factory_root}`

Directory that contains `.cursor/foundry/` (Foundry plugin bundle or a factory clone). Order:

1. **Skill-relative** — from any skill under `.cursor/skills/{name}/`, go up `../..` to the bundle/clone root; confirm `.cursor/foundry/cli/foundry.py` exists.
2. **Environment** — `workspace.org_repo_path_env` when that variable is set and the path exists.
3. **Sibling factory repo** — from `{app_folder}` when known: any sibling directory that contains `.cursor/foundry/cli/foundry.py` (including `../github-private` or `../.github-private` when those names are used).
4. **Ask the human once** — do not guess.

Set `{factory_root}` to that absolute path for all later factory Reads and CLI calls.

### 2. Resolve `{app_folder}`

Skip when the consuming skill already set `{app_folder}`.

1. **User prompt** — repo or folder name (`on Example.Api`, `@Example.Api/`).
2. **Workspace** — exactly one workspace root whose folder name is **not** `github-private` or `.github-private` → use it.
3. **`workspace.default_app_folder`** — when still unknown, load parent config once (step 3 uses `{factory_root}` from step 1; `--app-folder` optional):

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" config get --factory-root "{factory_root}" --role parent
```

Read `workspace.default_app_folder` from the JSON when non-empty.

4. **Ambiguous** — multiple app roots: list `workspace.app_folders` (from parent JSON if loaded) plus open workspace roots; **ASK HUMAN**; do not guess.

**Orchestrator note:** Board-pick and ticket-hint resolution stay in `foundry` / `jira-board-pick.md` — run those **before** bootstrap when Jira ticket labels/components name the app.

### 3. Load FactoryConfig

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" config get --factory-root "{factory_root}" --role {bootstrap_role} --app-folder "{app_folder}"
```

- Use the CLI stdout JSON as **FactoryConfig** for the rest of the consuming skill.
- On failure: stop and report `errorCode`, `message`, and `requiredInput` — do not invent defaults that contradict the CLI.
- Re-run when `{app_folder}` changes mid-run.

### 4. Hand off to consumer

The consuming skill reads:

- `{factory_root}` and `{app_folder}` from FactoryConfig (or from resolution above)
- Role-specific keys per [factory-config-packet.md](../../foundry/templates/factory-config-packet.md)

---

## Rules

- **Never** parse profile YAML in the agent — only `foundry.py config get`.
- **Never** hardcode `TICKET`, JQL, branch patterns, or template paths when FactoryConfig provides them.
- Prefer **one** `config get` per role per run; orchestrators may slice from a parent object instead of re-calling the CLI (see factory-config-packet.md).
- New factory-dependent skills: set `{bootstrap_role}`, link this file in the variables contract, add the role to `ROLE_KEYS` in `foundry_mechanics.py` if new keys are needed.

---

## New skill checklist

When adding a skill under `.cursor/skills/` that needs team variables:

1. Pick `{bootstrap_role}` (existing row in factory-config-packet, or extend `ROLE_KEYS` + profile + tests).
2. In the skill’s **Variables contract**, write: “Follow [factory-bootstrap/SKILL.md](../factory-bootstrap/SKILL.md) with `{bootstrap_role}` = `your-role`.”
3. Document which parent roles can substitute (skip bootstrap when passed).
4. Add a row to [foundry/README.md](../../foundry/README.md) Quick links if the skill is user-facing.
