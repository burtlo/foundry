---
name: branch-to-jira-task
description: Scan branch changes, create a Jira task, and complete the development workflow
---

# Branch to Jira task

This command scans and summarizes the current changes in your active branch, creates a Jira Task in the configured project backlog, and guides you through the development workflow to completion.

---

## STEP 0: Load FactoryConfig

When **FactoryConfig** is not already in the prompt, read and follow **[command-bootstrap.md](../foundry/templates/command-bootstrap.md)** with `{bootstrap_role}` = **`ticket-workflow`**.

Resolve `{app_folder}` from the workspace (the repo whose branch you are analyzing) before re-running `config get` with `--app-folder` when needed.

---

## STEP 1: Get Current User Information

**Instructions for Agent:**

Use the Atlassian MCP to fetch the current user's information.

```
Call the Atlassian MCP atlassianUserInfo to:
1. Get the current user's account information
2. Extract and store:
   - User's FIRST NAME for use in branch naming
   - User's ACCOUNT ID for Jira ticket reporter field
```

**Store the following for later use:**
- `{DeveloperFirstName}` - First name from display name (e.g., "Dan" from "Dan Smith")
- `{DeveloperAccountId}` - The user's Jira account ID

---

## STEP 2: Analyze Current Branch Changes

**Scan and summarize the changes in the active branch.**

### Step 2a: Get Current Branch Information

```text
git branch --show-current
git rev-parse --abbrev-ref origin/HEAD
```

`git rev-parse --abbrev-ref origin/HEAD` prints `origin/main` (or `origin/master`). Record `{DEFAULT_BRANCH}` as the **last path segment only** (`main` / `master`). Never use `origin/main` as `{DEFAULT_BRANCH}` for checkout, `git pull origin`, or `gh pr create --base`.

If `origin/HEAD` is missing, check:

```text
git show-ref --verify --quiet refs/remotes/origin/main
git show-ref --verify --quiet refs/remotes/origin/master
```

Use `main` if the first `show-ref` succeeds; otherwise `master`. Record `{CURRENT_BRANCH}` from `git branch --show-current`.

### Step 2b: Gather Change Statistics

```text
git diff --stat {DEFAULT_BRANCH}
git diff --name-status {DEFAULT_BRANCH}
git diff {DEFAULT_BRANCH}
```

### Step 2c: Analyze Changes

Categorize the changes:
- **Files Modified:** Count of files changed
- **Files Added:** Count of new files
- **Files Deleted:** Count of removed files
- **Key Patterns:** Identify what types of changes (API endpoints, services, tests, etc.)
- **Repository Context:** Extract repository name and solution information

---

## STEP 3: Generate Jira Task Content

**Auto-generate the Jira task content based on the analysis.**

### Task Title Generation

Generate a descriptive title based on:
- The types of files changed
- The primary feature or fix being implemented
- The repository/solution context

**Format:** `[Brief Action]: [Component/Feature] - [Context]`
**Examples:**
- `Add: CoworkerService name search endpoint`
- `Fix: UKG integration timeout handling`
- `Refactor: Repository layer for MDM queries`

### Description Content Template

Generate the description using this structure:

```markdown
## User Story

As a [role based on context - developer/API consumer/team member], 
I want to [action derived from the changes being made],
so that [benefit inferred from the changes].

## General Information

[Summary of what this task accomplishes based on the analyzed changes]

**Repository:** {repository name}
**Solution:** {solution name if applicable}

**Change Summary:**
- **Files Modified:** {count}
- **Files Added:** {count}
- **Files Deleted:** {count}

**Key Changes:**
- {List significant changes detected from the diff analysis}
- {Group by category: API changes, service changes, test additions, etc.}

**Note:** This task was auto-generated from branch analysis. Review and adjust as needed.

## Acceptance Criteria

- [ ] All code changes compile successfully (`dotnet build` passes)
- [ ] All existing tests continue to pass
- [ ] New functionality has appropriate test coverage
- [ ] Documentation updated (AGENTS.md) if needed
- [ ] PRD regenerated to reflect changes
- [ ] {Additional criteria based on detected change types}
```

---

## STEP 4: User Review and Edit

**Present the generated content to the developer for review.**

> "📝 **Generated Jira Task Content**
> 
> **Title:** {generated title}
> 
> **Description:**
> {generated description}
> 
> **Labels:** TechDebt/TechLed
> **Sprint:** (None - Backlog)
> 
> Would you like to:
> - **Create as-is** - Create the Jira task with this content
> - **Edit title** - Modify the task title
> - **Edit description** - Modify the description content
> - **Add criteria** - Add additional acceptance criteria
> - **Cancel** - Don't create the task"

**WAIT for developer input before proceeding.**

---

## STEP 5: Create Jira Task in Backlog

**Create the Jira task using the Atlassian MCP.**

### Step 5a: Create the Issue

```
Call createJiraIssue with:
- cloudId: from FactoryConfig `jira.cloud_id` (or `jira.site_url` per atlassian-integration.md)
- projectKey: from FactoryConfig `jira.project_key`
- issueTypeName: "Task"
- summary: {approved title}
- description: {approved description in Markdown format}
```

**IMPORTANT:** Do NOT set a sprint field - the task must be created in the backlog.

### Step 5b: Apply Labels

After creation, update the issue to add required labels:

```
Call editJiraIssue with:
- issueIdOrKey: {created issue key}
- fields: { 
    "labels": ["TechDebt/TechLed"]
  }
```

### Step 5c: Confirm Creation

Store the created ticket number for branch naming:
- `{JiraTicketNumber}` - The new ticket ID (e.g., TICKET-1234)

**Confirm with the developer:**

> "✅ **Jira Task Created**
> 
> **Ticket:** [{JiraTicketNumber}](https://example.atlassian.net/browse/{JiraTicketNumber})
> **Status:** Backlog (no sprint assigned)
> **Labels:** TechDebt/TechLed
> 
> Ready to proceed with development workflow?"

---

## STEP 6: Create Feature Branch

**Reference:** Read and follow `templates.create_branch` from FactoryConfig.

Use the `{DeveloperFirstName}` from Step 1 and `{JiraTicketNumber}` from Step 5.

---

## STEP 7: Implement the Code Changes

**Reference:** Read and follow `templates.implement` from FactoryConfig.

---

## STEP 8: Add Tests

**Reference:** Read and follow `templates.add_tests` from FactoryConfig (including **`Subject_Scenario_ExpectedOutcome`** naming and one assertion per independent fact when practical).

---

## STEP 9: Run Tests

**Reference:** Read and follow `templates.run_tests` from FactoryConfig.

---

## STEP 10: Update AGENTS.md Files

**Reference:** Read and follow `templates.update_docs` from FactoryConfig.

---

## STEP 11: Generate PRD

**Reference:** Read and follow `templates.generate_prd` from FactoryConfig.

---

## STEP 12: Developer Code Review

**Reference:** Read and follow `templates.code_review` from FactoryConfig.

---

## STEP 13: Commit and Push

**Reference:** Read and follow `templates.commit_push` from FactoryConfig.

---

## STEP 14: Create Pull Request

**Create the PR using GitHub CLI or provide the direct URL.**

### PR title (required)

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" pr-title --issue-key "{JiraTicketNumber}" --summary "{Jira Summary or approved task title}" --pattern "{git.pr_title_pattern}" --jira-enabled true
```

Use the stdout JSON `title` as `{resolved_pr_title}`. **Wrong vs right:** PR titles are **not** commit messages — never reuse the commit subject as `--title`.

| Wrong | Right |
|-------|-------|
| `feat(TICKET-2247): Upgrade Example.Api to .NET 10` | `{resolved_pr_title}` from `pr-title` |

Show `{resolved_pr_title}` to the developer before creating the PR.

### Default branch

`{DEFAULT_BRANCH}` from Step 2a, or run:

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" git default-branch --repo "{app_folder}"
```

### Step 14a: Check for GitHub CLI

```text
gh --version
```

### Step 14b: Create PR with GitHub CLI (Preferred)

If GitHub CLI is available, build `{pr_body_markdown}` (Summary, Jira Ticket, Changes Made, Testing, Checklist) then:

```text
gh pr create --title "{resolved_pr_title}" --body "{pr_body_markdown}" --base {DEFAULT_BRANCH}
```

### Step 14c: Alternative - Generate PR URL

If GitHub CLI is not available:

```text
git config --get remote.origin.url
```

Rewrite `git@github.com:` to `https://github.com/` and strip a trailing `.git` in-agent. Compare URL:

`{REPO_URL}/compare/{DEFAULT_BRANCH}...{DeveloperFirstName}/{JiraTicketNumber}?expand=1`

---

## Workflow Complete! 🎉

Summary of what was accomplished:
1. ✅ Identified developer ({DeveloperFirstName}) from Jira
2. ✅ Analyzed current branch changes
3. ✅ Generated Jira task content
4. ✅ Created Jira task in backlog: [{JiraTicketNumber}](https://example.atlassian.net/browse/{JiraTicketNumber})
5. ✅ Applied labels: TechDebt/TechLed
6. ✅ Created feature branch: {DeveloperFirstName}/{JiraTicketNumber}
7. ✅ Implemented code changes
8. ✅ Added tests (unit/integration/e2e)
9. ✅ All tests passing
10. ✅ AGENTS.md documentation updated
11. ✅ PRD generated/updated
12. ✅ Developer reviewed and approved changes
13. ✅ Code committed and pushed
14. ✅ PR created

**Next Steps:**
- Wait for code review from team
- Address any review feedback
- Merge when approved

