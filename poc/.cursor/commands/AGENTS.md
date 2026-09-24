# Cursor Commands — Foundry

> **For AI Agents:** Catalog of shared Cursor commands, templates, and workflows shipped with the Foundry plugin.

---

## Available Commands

| Command | File | Description |
|---------|------|-------------|
| `/ticket-workflow` | `ticket-workflow.md` | Complete development workflow from Jira ticket to PR |
| `/branch-to-jira-task` | `branch-to-jira-task.md` | Scan branch changes, create a Jira task, and complete development workflow |
| `/documentation-workflow` | `documentation-workflow.md` | Create AGENTS.md documentation and generate PRD |
| `/prd-regenerate` | `prd-regenerate.md` | Regenerate the unified PRD from existing AGENTS.md files |
| `/foundry` | `foundry.md` | Software Factory — registry-driven state machine with durable run state |
| `/foundry-app-bootstrap` | `foundry-app-bootstrap.md` | Discover, create, and validate an app-owned Foundry manifest |

---

## Templates

Templates are stored in the `templates/` folder and shared across workflows.

### Documentation Templates

| Template | File | Purpose |
|----------|------|---------|
| AGENTS.md Templates | `templates/agents-md-templates.md` | Entry point classification, root/entry point AGENTS.md templates, required fields checklist |
| PRD Generator Template | `templates/prd-generator-template.md` | PRD generator prompt template, output structure, Mermaid diagrams |

### Workflow Step Templates

Shared development workflow steps used by `ticket-workflow` and `branch-to-jira-task`:

| Template | Description |
|----------|-------------|
| `templates/create-branch-step.md` | Detect default branch, checkout, pull latest, create feature branch |
| `templates/implement-changes-step.md` | Code implementation guidelines, build verification, developer confirmation |
| `templates/add-tests-step.md` | Discover test projects; add unit/integration/E2E tests; **`Subject_Scenario_ExpectedOutcome`** naming |
| `templates/run-tests-step.md` | Run all tests, handle failures, confirm passing |
| `templates/update-docs-step.md` | Update AGENTS.md files based on changes made |
| `templates/generate-prd-step.md` | Check/create PRD generator, execute PRD generation |
| `templates/code-review-step.md` | Show change summary, git diff, developer approval |
| `templates/commit-push-step.md` | Stage changes, commit with conventional message, push |

### Template Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `{DeveloperFirstName}` | Developer's first name | Jira user info |
| `{JiraTicketNumber}` | Jira ticket ID (e.g., TICKET-1234) | Selected/created ticket |
| `{Brief description}` | Very brief PR title suffix from Jira Summary | Jira ticket Summary |
| `{DEFAULT_BRANCH}` | Short default branch name (`main` / `master`, never `origin/main`) | `foundry.py git default-branch` (see [command-bootstrap.md](../foundry/templates/command-bootstrap.md)) |
| `{factory_root}`, `{app_folder}` | Factory bundle path and target app repo | FactoryConfig via [command-bootstrap.md](../foundry/templates/command-bootstrap.md) at command Step 0 |

**PR title format:** run `foundry.py pr-title` with `git.pr_title_pattern` from FactoryConfig (Foundry profile).

---

## Software Factory

The **foundry** skill is the Software Factory orchestrator (durable runs, registry-driven gates, subagents including **devops-builder** for GitHub Actions SHA pinning and **`gh`-based CI failure investigation). The **bug-squash** skill orchestrates Azure Monitor triage → `codebase-researcher` (`bug_triage`) → `backend-builder` / `client-builder` (`propose_fix`) → `story-writer` with engineer gates. Configuration lives in `.cursor/foundry/profiles/*.yaml`.

| Artifact | Path |
|----------|------|
| Setup guide | `docs/software-factory-setup.md` |
| Team profile | `.cursor/foundry/profiles/default.yaml` |
| Local markdown tickets | `.cursor/foundry/docs/local-tickets.md` |
| Orchestrator skill | `.cursor/skills/foundry/SKILL.md` |
| Flow registry | `.cursor/foundry/flows/factory-flow.yaml` |
| State engine CLI | `.cursor/foundry/cli/foundry.py` |
| Subagents | `.cursor/agents/` |
| Skills | `.cursor/skills/` (authoring: `write-for-agents`) |

**Kickoff example (ticket list first):**

```text
Use foundry. Pick from the Jira board.
```

**Bug squash example:**

```text
Use bug-squash on your-app.
```

Editing the flow means editing `factory-flow.yaml` and the matching `steps/*.md` together, then regenerating the diagram. The `Foundry Flow Check` workflow fails the PR when they disagree.

```text
Use foundry. Pick from the Jira board.
```

---

## Setup Requirements

### Atlassian integration (Jira)

Foundry and ticket workflows need Jira access. Use this **fallback order** (see `.cursor/foundry/docs/atlassian-integration.md`):

1. **Atlassian Cursor plugin** (recommended) — install from [Cursor Marketplace → Atlassian](https://cursor.com/marketplace/atlassian); **Settings → MCP** → enable **plugin-atlassian-atlassian** for this workspace; complete OAuth on first use.
2. **HTTP MCP fallback** — if plugin MCP is errored or unavailable, add to `%USERPROFILE%\.cursor\mcp.json` (Windows) or `~/.cursor/mcp.json` (macOS/Linux):

```json
{
  "mcpServers": {
    "atlassian": {
      "url": "https://mcp.atlassian.com/v1/mcp/authv2"
    }
  }
}
```

Runtime id: **`user-atlassian`**. On first use in an Agent chat, the agent must call **`mcp_auth`** `{}` on **`user-atlassian`** when STATUS says authentication is required (browser OAuth). Then `atlassianUserInfo` and Jira tools work.

3. **Manual Jira URL** — if both fail, paste a browse URL or issue key when prompted (e.g. `https://example.atlassian.net/browse/TICKET-1234`).

**Verify connection:**

> Ask the agent to call `atlassianUserInfo`, or start foundry and confirm your name appears in the ticket packet.

### Cursor Workspace

**Run:** enable the **Foundry** plugin and open the app repo (`/foundry`). Cloning this repo is not required to run.

**Contribute:** open a multi-root workspace with the factory clone plus one or more app repos. See `.cursor/foundry/README.md`.

---

## How to Use These Commands

### Option 1: Plugin (Recommended)

Enable **Foundry** and open the app repo. Do not copy commands into the app.

### Option 2: Multi-root workspace (contribute)

Keep commands in the factory clone only. Reference via `@{factory}/.cursor/commands/...` or use the foundry skill with `resolve_templates_from_org: true` in the team profile.

### Option 3: User-level commands

Windows: `Copy-Item -Recurse {clone}\.cursor\commands $env:USERPROFILE\.cursor\commands`

macOS/Linux: `cp -r {clone}/.cursor/commands/ ~/.cursor/commands/`

---

## Contributing

To add or modify commands:
1. Create/edit the `.md` file in this folder
2. Add YAML frontmatter (`name`, `description`) at the top — required for plugin slash-menu discovery
3. Update this AGENTS.md with the new command
4. Create a PR for review
5. Once merged to `main`, the **Bump Cursor plugin version** workflow auto-increments semver when `.cursor/**` changes; **Refresh** the Foundry marketplace listing if slash commands do not appear after reload

### Command Best Practices

- **Solution Agnostic**: Don't hardcode project names or paths
- **Discover Dynamically**: Use commands to discover project structure
- **Be Interactive**: Guide developers through decisions
- **Reference AGENTS.md**: Validate against project documentation
