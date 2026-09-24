---
name: write-for-agents
description: >-
  Author Cursor skills, slash commands, factory templates, alwaysApply rules,
  and AGENTS.md so agents follow them. Covers what binds (fences, rules) vs
  what is ignored (nags, tool tutorials), dual-shell fences, discovery as
  goal+glob, and Foundry plugin packaging. Use when creating or editing
  files under .cursor/skills, .cursor/commands, .cursor/agents, .cursor/rules,
  .cursor/foundry, AGENTS.md, or when asked to write a skill, command, or
  agent instruction file.
---

# Write for agents

Use Cursor's **create-skill** for SKILL.md structure (frontmatter, description, length). This skill is the **Foundry / factory overlay**: how instructions bind, dual-shell fences, and where files go in this plugin.

Canonical shell constraints: `.cursor/rules/agent-shell.mdc` (`alwaysApply: true`). Do not restate them in every file.

## Pick the artifact

| Need | Put it here | Ships with plugin via |
|------|-------------|------------------------|
| Every-turn constraint (shell, search) | `.cursor/rules/*.mdc` `alwaysApply: true` | `"rules": ".cursor/rules"` |
| Named workflow the user or parent launches | `.cursor/skills/{name}/SKILL.md` | `"skills": ".cursor/skills"` |
| Slash command | `.cursor/commands/{name}.md` (YAML `name` + `description`) | `"commands": ".cursor/commands"` |
| Subagent | `.cursor/agents/{name}.md` | `"agents": ".cursor/agents"` |
| Factory config / step templates | `.cursor/foundry/` | marketplace `"source": "."` |
| App facts (ports, owners, integrations) | `{app}/AGENTS.md` | not this repo |
| Human onboarding | `README.md`, `docs/`, `Documentation/` | clone / GitHub |

Do **not** bump `.cursor-plugin` versions in the PR. Merge to `main` runs the bump workflow.

## What binds vs what is ignored

| Surface | Agents do this | Use for |
|---------|----------------|---------|
| Copy-paste **command fences** | Run the first valid command | Steps the agent must execute |
| **`alwaysApply` rules** | Injected every turn | Fragile constraints (shell, no `/dev/null`) |
| “Follow X / don’t switch shells / use the Glob tool” | Skip | Never — nags do not bind |
| README / setup | Skip (humans) | Prerequisites, plugin vs clone |

If a footnote did not change behavior last time, deleting it is the fix. Encoding the command correctly is the replacement.

## Command fences

| Case | How to write it |
|------|-----------------|
| Portable CLI, same argv | One unlabeled or `text` fence: `git status`, `dotnet test`, `gh pr create --title "..." --body "..." --base {branch}` (single line, no `\`) |
| Foundry CLI (orchestrator) | `foundry-invoke` fence: argv tail only, one line, no `python` / `foundry.py` / `{foundry_cli}`. Parent prepends `foundry_cli` from run context JSON. See `.cursor/skills/foundry/SKILL.md`. |
| Syntax cannot be unified | Two short fences. Run **only** the fence for the current shell. PowerShell **5.1** only (no `&&`). Example: `git commit` here-string vs bash `-m` |
| File discovery | Goal + pattern (`**/AGENTS.md`, `*.csproj` containing `Microsoft.NET.Test.Sdk`). **Delete** `find` / `grep` / `xargs` / `2>/dev/null` fences |
| Redirects | Never `/dev/null` in PowerShell (`C:\dev\null`). PS: `2>$null`. Bash `/dev/null` only inside `bash` fences |

Scripts: Windows `powershell -NoProfile -File path.ps1`. macOS/Linux `bash path.sh`. **Category 4 factory mechanics** (config parse, issue-key, PR title, default branch, delivery-check, staged-secrets-check, build/test argv): the Python CLI at `.cursor/foundry/cli/foundry.py` plus its tests are the source of truth. Markdown becomes “call this command” plus policy. Dual-shell twins remain only for existing sync-prd validators.

Copy YAML/templates with **Read + Write**. Do not `cp` / `Copy-Item`.

Secrets from Azure CLI: keep the value in a **shell variable**, print only extracted fields. Never `az keyvault secret show ... -o tsv` as a standalone fence (stdout is logged).

Default branch: run `python "{factory_root}/.cursor/foundry/cli/foundry.py" git default-branch --repo "{app_folder}"` (parent). Do not teach agents to take the last path segment of `origin/HEAD` in prose.

Staged secrets (Step 8, after `git add`, before `git commit`): run `python "{factory_root}/.cursor/foundry/cli/foundry.py" git staged-secrets-check --repo "{app_folder}" --factory-root "{factory_root}"`. Patterns default in the CLI; override in the team profile `git.staged_secrets_check` (`pattern` replaces default; `extra_patterns` ORs onto default). There is no Cursor session hook — agents must run this explicitly.

## AGENTS.md and long instruction files

- **Facts**: tables, field names, ports, workflow names. Not interviews or “run this bash to discover X”.
- **Commands**: portable argv from the app’s real scripts (`dotnet build`, `dotnet test`).
- **Secrets**: NEVER rows for passwords, user IDs, full connection strings (see `templates/agents-md-templates.md`).
- **Do not** teach Glob/Grep by name. Omit the Unix discovery fence; native file tools are enough.
- Human first-week setup belongs in README / `Documentation/`, not in the agent-loaded dump.

Regenerating app AGENTS.md / PRDs is still **documentation-workflow**. This skill only constrains **phrasing** of new or edited agent text.

## New skill in this plugin (checklist)

1. Folder `.cursor/skills/{kebab-name}/SKILL.md` — that is enough to ship (no `plugin.json` edit).
2. Frontmatter: `name`, `description` (third person, WHAT + WHEN, trigger terms). Omit `disable-model-invocation` when the agent should auto-pick from context; set `true` when only a parent skill should launch it.
3. Keep SKILL.md short; link one level deep to templates under `.cursor/foundry/` or `.cursor/commands/templates/`.
4. **Team variables:** if the skill needs profile settings and is not always launched by `foundry` / `bug-squash`, do **not** inline bootstrap logic. In the variables contract, link [factory-bootstrap/SKILL.md](../factory-bootstrap/SKILL.md) with `{bootstrap_role}` set to an existing row in [factory-config-packet.md](../../foundry/templates/factory-config-packet.md). Add a new `ROLE_KEYS` entry in `foundry_mechanics.py` + tests only when the skill needs keys no role exposes yet. Library skills (like factory-bootstrap) use `disable-model-invocation: true`.
5. **Slash commands:** if the command needs team variables, add Step 0 linking [command-bootstrap.md](../../foundry/templates/command-bootstrap.md) with the command’s `{bootstrap_role}` (not `parent`). Reuse an existing role when the key slice matches; add `ROLE_KEYS` + tests only for a new minimal slice.
6. If the skill runs a **new Category 4 mechanic** (config, titles, branches, delivery-check, staged-secrets-check, build/test argv), add it to `.cursor/foundry/cli/foundry.py` and tests — do not add another `.ps1`/`.sh` twin. Dual-shell twins remain only for existing sync-prd validators.
7. Optional catalog: row in `.cursor/foundry/README.md` Quick links. `.cursor/commands/AGENTS.md` is the command catalog, not every skill.

## Examples

**Bad:** a nag (“use Git Bash”) plus a `find … 2>/dev/null` fence. Agents copy the fence; PowerShell creates `C:\dev\null`. The nag does nothing.

**Good:** `Find all **/AGENTS.md in the app repo.` No discovery fence, no tool tutorial.

**Bad:** only `bash "{org_repo_path}/.cursor/foundry/scripts/validate-sync-prd-caller.sh"`.

**Good (parent):** `python "{factory_root}/.cursor/foundry/cli/foundry.py" prd-sync validate --repo "{app_folder}" --factory-root "{factory_root}"`. Dual-shell `.ps1`/`.sh` fences remain only for the existing validator scripts when invoked directly.
