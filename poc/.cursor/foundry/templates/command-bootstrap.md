# Command bootstrap

Legacy slash commands load **role-scoped FactoryConfig** via [factory-bootstrap/SKILL.md](../../skills/factory-bootstrap/SKILL.md). They do **not** parse `team-variables.md` and do **not** use the `parent` role (full YAML).

When **FactoryConfig** is already in the prompt (e.g. launched from **foundry**), skip bootstrap and use that JSON.

---

## Role map

| Command | `{bootstrap_role}` | Keys loaded |
|---------|-------------------|-------------|
| `/ticket-workflow` | `ticket-workflow` | `atlassian`, `jira`, `git`, `jira_transitions`, `workspace`, dev step `templates.*`, `{factory_root}`, `{app_folder}` |
| `/branch-to-jira-task` | `ticket-workflow` | Same as ticket workflow (creates a Jira task, then runs the same dev chain) |
| `/documentation-workflow` | `documentation-workflow` | `workspace`, docs/PRD/sync `templates.*`, `{factory_root}`, `{app_folder}` |

CLI source of truth for slices: `ROLE_KEYS` in `foundry.py` and [factory-config-packet.md](./factory-config-packet.md).

---

## Procedure (every command)

1. If **FactoryConfig** is in the prompt and satisfies the command’s needs, use it.
2. Else follow [factory-bootstrap/SKILL.md](../../skills/factory-bootstrap/SKILL.md) with the `{bootstrap_role}` from the table above.
3. Resolve `{app_folder}` (workspace single app root → `workspace.default_app_folder` → ask human). Re-run `config get` with `--app-folder` when `{app_folder}` was unknown on the first call.
4. For Jira search: substitute `{{project_key}}` in `jira.pick_list_jql` with `jira.project_key`. Show resolved JQL before `searchJiraIssuesUsingJql`. **Never** hardcode project keys.
5. For step templates: read paths from `templates.*` in FactoryConfig (already resolved when `workspace.resolve_templates_from_org` is true).

---

## Atlassian

Resolve MCP connection per [atlassian-integration.md](../atlassian-integration.md) using `atlassian.*` from FactoryConfig.

---

## Factory CLI (common)

| Need | foundry-invoke argv tail |
|------|--------------------------|
| Default branch | `git default-branch --repo "{app_folder}"` |
| Feature branch | `branch-name` + `branch create` (see `templates.create_branch`) |
| Build / test | `build` / `test` |
| PR title | `pr-title --issue-key ... --summary ... --pattern "{git.pr_title_pattern}" --jira-enabled true` |
| Staged secrets | `git staged-secrets-check` (after `git add`, before `git commit`) |
| Sync-prd caller | `prd-sync validate --repo "{app_folder}" --factory-root "{factory_root}"` |

Prepend `foundry_cli` from run context. Do not put `python` / `foundry.py` inside fences.
