# FactoryConfig packet

Fill this JSON (or the CLI equivalent), then pass the **role-scoped** object to subagents or use it in standalone skills. Do not hand-parse `team-variables.md`.

| Caller | How to obtain FactoryConfig |
|--------|----------------------------|
| **Orchestrators** (`foundry`, `bug-squash`) | Parent loads once at kickoff; pass slices on each subagent launch |
| **Standalone factory skills** (`build-with-tests`, future skills) | Follow [factory-bootstrap/SKILL.md](../../skills/factory-bootstrap/SKILL.md) with the skill’s `{bootstrap_role}` |
| **Slash commands** (`ticket-workflow`, `branch-to-jira-task`, `documentation-workflow`) | Follow [command-bootstrap.md](./command-bootstrap.md) → factory-bootstrap with the command’s role (not `parent`) |
| **Subagents** (default) | Receive JSON from parent; if omitted, stop and ask parent (or follow factory-bootstrap when that agent is updated to support standalone) |

**CLI (source of truth):**

```foundry-invoke
config get --factory-root "{factory_root}" --role {role} --app-folder "{app_folder}"
```

Until the CLI is invoked, the caller may fill the same shape after a single `config get` (do not re-parse YAML by hand).

Template paths in the packet must be **resolved absolute or factory-root-relative paths that exist**, not the unresolved `templates.*` strings from YAML.

---

## Roles (pass only these keys)

| Role | Keys |
|------|------|
| `parent` | Full parsed YAML after defaults (parent working copy), plus `{app_folder}`, `{factory_root}` |
| `backend-builder` | `templates.implement`, `templates.add_tests`, `templates.run_tests`; `{app_folder}`, `{factory_root}` |
| `client-builder` | `templates.implement`, `templates.add_tests`, `templates.run_tests`; `{app_folder}`, `{factory_root}` |
| `feature-builder` | `templates.implement`, `templates.add_tests`, `templates.run_tests`; `{app_folder}`, `{factory_root}` |
| `devops-builder` | `devops.*`, `org.display_name`; `{app_folder}`, `{factory_root}` |
| `documentation-writer` | `templates.documentation_workflow`, `templates.sync_prd_caller`, `templates.sync_prd_step`, `templates.sync_prd_validate_script`, `templates.sync_prd_validate_script_posix`; `analysis.*` (deliverable sections + Confluence settings for analysis mode A2); `{app_folder}`, `{factory_root}` |
| `story-writer` | `org.required_labels`, `jira.project_key`, `story_writer.*`, `analysis.*`, `bug_squash.*` (when that mode); `{app_folder}`, `{factory_root}` |
| `codebase-researcher` | `{app_folder}`, `{factory_root}` only |
| `implementation-validator` | `org.required_labels`, `jira.project_key`; `{app_folder}`, `{factory_root}` |
| `build-with-tests` | `templates.implement`, `templates.add_tests`, `templates.run_tests`; `{app_folder}`, `{factory_root}` |
| `ticket-workflow` | `atlassian`, `jira`, `git`, `jira_transitions`, `workspace`, dev step `templates.*` (create_branch through commit_push); `{app_folder}`, `{factory_root}` |
| `documentation-workflow` | `workspace`, `templates.documentation_workflow`, `templates.generate_prd`, `templates.update_docs`, sync-prd `templates.*`; `{app_folder}`, `{factory_root}` |

If `FactoryConfig` is omitted from a subagent launch, the subagent **stops** and asks the parent (standalone skills and slash commands use [factory-bootstrap](../../skills/factory-bootstrap/SKILL.md) or [command-bootstrap](./command-bootstrap.md) instead).

---

## Example — `backend-builder`

```json
{
  "role": "backend-builder",
  "app_folder": "Example.Api",
  "factory_root": "C:/repos/ORG/factory",
  "templates": {
    "implement": ".cursor/commands/templates/implement-changes-step.md",
    "add_tests": ".cursor/commands/templates/add-tests-step.md",
    "run_tests": ".cursor/commands/templates/run-tests-step.md"
  }
}
```

---

## Example — `codebase-researcher`

```json
{
  "role": "codebase-researcher",
  "app_folder": "Example.Api",
  "factory_root": "C:/repos/ORG/factory"
}
```

---

## Builder AGENTS.md headings

When launching `backend-builder`, `client-builder`, or `feature-builder`, point them at these headings in `{app_folder}/AGENTS.md` (and the entry-point AGENTS.md if the brief names that project):

- Policy
- Key Patterns
- Authentication / Security
- Data Contracts
- Common Commands (parent may instead attach `foundry.py project-context --purpose implementation` JSON)

Do not tell builders to ingest CI/CD tables, mermaid architecture diagrams, or ownership TBD rows unless the scoped brief needs them.
