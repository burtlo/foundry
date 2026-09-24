---
name: ticket-workflow
description: Complete development workflow from Jira ticket to PR
---

# Ticket workflow

This command guides you through the complete development workflow: from selecting a Jira ticket to creating a pull request. This workflow is designed to work with any .NET solution.

---

## STEP 0: Load FactoryConfig

When **FactoryConfig** is not already in the prompt (not launched from foundry), read and follow **[command-bootstrap.md](../foundry/templates/command-bootstrap.md)** with `{bootstrap_role}` = **`ticket-workflow`**.

Resolve `{app_folder}` before re-running `config get` with `--app-folder` when it was unknown on the first call.

Use FactoryConfig for Jira, git, transitions, Atlassian MCP settings, and resolved `templates.*` paths. **Never** parse `team-variables.md` or hardcode project keys.

---

## STEP 1: Fetch Sprint Tickets from Jira

**Instructions for Agent:**

Use the Atlassian MCP (Model Context Protocol) to fetch the current user's information and their assigned tickets.

### Step 1a: Get Current User Info

```
Call the Atlassian MCP atlassianUserInfo to:
1. Get the current user's account information
2. Extract and store:
   - User's FIRST NAME for use in branch naming (Step 4)
   - User's ACCOUNT ID for ticket assignment (Step 2)
```

**Store the following for later use:**
- `{DeveloperFirstName}` - First name from display name (e.g., "Dan" from "Dan Smith")
- `{DeveloperAccountId}` - The user's Jira account ID (needed to assign tickets)

### Step 1b: Fetch Sprint Tickets

**CRITICAL: Build JQL only from FactoryConfig.** Substitute `{{project_key}}` in `jira.pick_list_jql` with `jira.project_key`. Show the resolved JQL to the developer before searching.

```
Call the Atlassian MCP searchJiraIssuesUsingJql to fetch tickets from the current sprint:

Use the resolved pick-list JQL from FactoryConfig (after {{project_key}} substitution).

Respect jira.pick_list_max_results when set.

Display them in a numbered list with:
   - Ticket ID (e.g., {project_key}-1234)
   - Title/Summary
   - Status (To Do / In Progress)
   - Type (Bug, Story, Task)
   - Priority
   - Assignee (if assigned)
   - Story Points (if available)
```

**CRITICAL: Error Handling for Jira Search**

**VERIFICATION:** Before calling `searchJiraIssuesUsingJql`, confirm the JQL starts with `project = {jira.project_key}`. If not, fix the query from FactoryConfig — do not proceed with a hardcoded project key.

**If `searchJiraIssuesUsingJql` fails or returns an error:**
> "🚨 **Jira Search Error**
> 
> Unable to search Jira tickets. This could be due to:
> - Jira MCP authentication failure
> - Insufficient permissions to search the configured project (`{jira.project_key}`)
> - Invalid JQL query syntax
> - Network/connectivity issues
> 
> **Please check:**
> 1. The JQL matches `jira.pick_list_jql` from FactoryConfig (with `{{project_key}}` substituted)
> 2. Your Jira account has access to project `{jira.project_key}`
> 3. Atlassian MCP is properly configured (see `atlassian-integration.md`)
> 4. Network connection is stable
> 
> **Error details:** {error message from MCP}
> 
> **Workflow cannot continue.** Please resolve the issue and try again."

**If tickets from other projects are returned:**
> "🚨 **Incorrect Project Filter Detected**
> 
> The JQL returned tickets outside project `{jira.project_key}`. Rebuild the query from FactoryConfig `jira.pick_list_jql` and retry.
> 
> **Resolved JQL used:** `{resolved_jql}`"

**Group the results by status:**

> "Hi {DeveloperFirstName}! Here are the available tickets for this sprint:
> 
> **📋 To Do (Available to pick up):**
> 1. {TICKET-ID} - {Title} ({Type}, {Priority})
> 2. ...
> 
> **🔄 In Progress (Assigned to you):**
> 3. {TICKET-ID} - {Title} ({Type}, {Priority})
> 4. ...
> 
> Which ticket would you like to work on? (Enter the number or ticket ID)"

---

## STEP 2: Analyze Ticket Requirements

Once the developer selects a ticket:

### Step 2a: Claim Ticket (if needed)

**If the selected ticket is in "To Do" status:**

1. **Assign the ticket** to the current user using `editJiraIssue`:
   ```
   Call editJiraIssue with:
   - issueIdOrKey: {selected ticket ID}
   - fields: { "assignee": { "accountId": "{DeveloperAccountId from Step 1a}" } }
   ```

2. **Transition the ticket to "In Progress"** using `transitionJiraIssue`:
   ```
   First, call getTransitionsForJiraIssue to get available transitions
   Then, call transitionJiraIssue with the "In Progress" transition ID
   ```

3. **Confirm the update:**
   > "✅ Ticket {JiraTicketNumber} has been assigned to you and moved to 'In Progress'."

**If the ticket is already "In Progress" and assigned to the developer:**
   > "✅ Ticket {JiraTicketNumber} is already assigned to you and in progress."

### Step 2b: Fetch Ticket Details

1. **Fetch full ticket details** from Atlassian MCP including:
   - Full description
   - Acceptance criteria
   - Linked tickets/dependencies
   - Comments/discussion

2. **Display the Acceptance Criteria explicitly:**

> **Acceptance Criteria for {JiraTicketNumber}:**
> 
> - [ ] Criterion 1: {First acceptance criterion from the ticket}
> - [ ] Criterion 2: {Second acceptance criterion from the ticket}
> - [ ] Criterion 3: {Third acceptance criterion from the ticket}
> - [ ] *(continue for all acceptance criteria)*

3. **Summarize the requirements** for the developer:
   - What needs to be built/fixed
   - Expected behavior
   - Any technical constraints mentioned

---

## STEP 3: Verify AGENTS.md Files Exist & Check for Conflicts

**Before making any code changes, verify AGENTS.md documentation exists and validate requirements against it.**

### Template Reference

**All templates, checklists, and defaults are centralized in `templates/agents-md-templates.md`:**
- Entry Point Project Types (what gets an AGENTS.md)
- Root AGENTS.md Template (27 required fields)
- Entry Point AGENTS.md Template (12 required sections)
- IoT Team Defaults (Tech Owner, Dev Team, Source Control)
- Auto-Discovery Commands
- Audit Checklists

### Step 3a: Discover Solution Structure & Identify Entry Points

1. **Find the solution file** (`.sln`) in the workspace
2. **List all projects** in the solution
3. **Identify entry point projects** using the classification table from `templates/agents-md-templates.md`:

| Project Type | Pattern Examples | Gets AGENTS.md |
|--------------|------------------|----------------|
| **API/Backend** | `*.Api`, `*.Functions`, `*.Web.Api`, `*.Http.*` | ✅ Yes |
| **Frontend UI** | `*.PWA`, `*.Admin`, `*.Web`, `*.Blazor`, `*.UI` | ✅ Yes |
| **Worker/Service** | `*.Worker`, `*.Jobs`, `*.Processor`, `*.Listener` | ✅ Yes |
| **Console App** | `*.Console`, `*.CLI` | ✅ Yes |
| Class Library | `*.Models`, `*.Data`, `*.Services`, `*.Common`, `*.Shared`, `*.Client` | ❌ No |
| Tests | `*.Tests`, `*.UnitTests`, `*.E2E.Tests` | ❌ No |

4. **Check for AGENTS.md files** in:
   - Root directory (main `AGENTS.md`)
   - Each **entry point** project directory only

### Step 3b: Create Missing AGENTS.md Files

**CRITICAL: The agent MUST actually create the files using the write/file creation tool. Do not just show templates - CREATE the files.**

**Reference:** All templates are centralized in `templates/agents-md-templates.md`

**If AGENTS.md files are missing, you have two options:**

#### Option A: Quick Creation (Minimal Documentation)

For quick ticket work, create minimal AGENTS.md files with basic structure.

1. **Read the templates** from `templates/agents-md-templates.md`
2. **Use the Root AGENTS.md Template** for the solution root
3. **Use the Entry Point AGENTS.md Template** for each entry point project
4. **Apply IoT Team Defaults** from the templates:
   - Tech Owner: `IoT`
   - Dev Team: `IoT`
   - Source Control: `GitHub`

**Auto-discover values using goals from `templates/agents-md-templates.md`:** solution name from `**/*.sln`; `<TargetFramework>` in `*.csproj`; authentication (`Okta`, `Azure.Identity`, `IdentityServer`) in `*.csproj`; infrastructure (`KeyVault`, `Cosmos`, `ServiceBus`, `SignalR`) in `*.csproj` / `*.json`.

**Populate templates with discovered values and create the files.**

#### Option B: Full Documentation (Recommended)

For comprehensive documentation with all 27 organizational metadata fields, run the **documentation-workflow** command:

> "This repository is missing comprehensive AGENTS.md documentation.
> 
> Would you like to:
> - **Quick create** - Create minimal AGENTS.md files to proceed with the ticket (Option A)
> - **Full documentation** - Run the documentation-workflow to create complete documentation with all 27 required metadata fields (Option B)
> 
> Note: Full documentation captures ownership, security, compliance, and business impact information required for organizational compliance."

#### After Creating Files

**Use the audit checklist from `templates/agents-md-templates.md`** to verify completeness:
- Root AGENTS.md: 27 required fields
- Entry Point AGENTS.md: 12 required sections

**Present to the developer:**
> "I've created the following AGENTS.md files for this solution's entry points:
> - {list of created files with full paths}
> 
> **IoT Defaults Applied:**
> - Tech Owner: `IoT`
> - Dev Team: `IoT`
> - Source Control: `GitHub`
> 
> Please review them and let me know if any changes are needed before we proceed.
> 
> Note: Class libraries ({list}) are documented within their parent entry point's AGENTS.md."

**WAIT for developer approval before proceeding.**

### Step 3c: Check for Conflicts

**Once AGENTS.md files exist (or were just created), validate the Jira requirements against them.**

**Conflict Types to Check:**

1. **Architecture Violations**
   - Does the change violate documented layer boundaries?
   - Does it bypass established patterns?

2. **Data Model Conflicts**
   - Does it conflict with documented entity schemas?
   - Does it violate documented data strategies?

3. **Business Logic Conflicts**
   - Does it conflict with documented business rules?
   - Does it change documented behavior without updating docs?

4. **Pattern Violations**
   - Does it introduce patterns that conflict with established conventions?
   - Does it duplicate existing functionality?

**If Conflicts Are Found:**

> "⚠️ **Potential Conflicts Detected**
> 
> The Jira ticket requirements may conflict with the following documented patterns:
> 
> 1. [Describe conflict 1]
> 2. [Describe conflict 2]
> 
> **Options:**
> - **Proceed anyway** - The AGENTS.md may need updating as part of this work
> - **Clarify with team** - Discuss the conflict before proceeding
> - **Choose different ticket** - Select a different ticket to work on
> 
> What would you like to do?"

**If No Conflicts:**

> "✅ No conflicts detected with documented patterns in AGENTS.md files. Ready to proceed with implementation."

---

## STEP 4: Create Feature Branch

**Note:** The developer's first name (`{DeveloperFirstName}`) was captured from Jira in Step 1 and will be used for the branch name.

**Reference:** Read and follow `templates.create_branch` from FactoryConfig (same content as `templates/create-branch-step.md`).

Use the `{DeveloperFirstName}` from Step 1 and `{JiraTicketNumber}` from the selected ticket.

---

## STEP 5: Implement the Code Changes

Work with the developer to implement the required changes.

**Reference:** Read and follow `templates.implement` from FactoryConfig.

---

## STEP 6: Add Tests

Based on the changes made, add appropriate tests.

**Reference:** Read and follow `templates.add_tests` from FactoryConfig (including **`Subject_Scenario_ExpectedOutcome`** naming and one assertion per independent fact when practical).

---

## STEP 7: Run Tests

Discover and run all test projects in the solution.

**Reference:** Read and follow `templates.run_tests` from FactoryConfig.

---

## STEP 8: Update AGENTS.md Files

Based on the changes made, update relevant AGENTS.md files.

**Reference:** Read and follow `templates.update_docs` from FactoryConfig.

---

## STEP 9: Generate PRD from AGENTS.md Files

**ALWAYS generate/update the PRD after updating AGENTS.md files. This step is mandatory.**

**Reference:** Read and follow `templates.generate_prd` from FactoryConfig.

---

## STEP 10: Developer Code Review

**CRITICAL: All changes must be reviewed by the developer BEFORE committing or pushing.**

**Reference:** Read and follow `templates.code_review` from FactoryConfig.

---

## STEP 11: Commit and Push

**Only proceed after developer approval in Step 10.**

**Reference:** Read and follow `templates.commit_push` from FactoryConfig.

---

## STEP 12: Create Pull Request

**Create the PR using GitHub CLI or provide the direct URL.**

### PR title (required)

Run the factory CLI (do not hand-build the title):

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" pr-title --issue-key "{JiraTicketNumber}" --summary "{Jira Summary}" --pattern "{git.pr_title_pattern}" --jira-enabled true
```

Use the stdout JSON `title` as `{resolved_pr_title}`. **Wrong vs right:** PR titles are **not** commit messages — never reuse the commit subject as `--title`.

| Wrong | Right |
|-------|-------|
| `feat(TICKET-2247): Upgrade Example.Api to .NET 10` | `{resolved_pr_title}` from `pr-title` |

Show `{resolved_pr_title}` to the developer before creating the PR.

### Default branch

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" git default-branch --repo "{app_folder}"
```

Record the short name as `{DEFAULT_BRANCH}` (`main` / `master` — never `origin/main`).

### Step 12a: Check for GitHub CLI

```text
gh --version
```

### Step 12b: Create PR with GitHub CLI (Preferred)

If GitHub CLI is available, build `{pr_body_markdown}` (Summary, Jira Ticket, Changes Made, Testing, Checklist) then:

```text
gh pr create --title "{resolved_pr_title}" --body "{pr_body_markdown}" --base {DEFAULT_BRANCH}
```

### Step 12c: Alternative - Generate PR URL

If GitHub CLI is not available:

```text
git config --get remote.origin.url
```

Rewrite `git@github.com:` to `https://github.com/` and strip a trailing `.git` in-agent. Compare URL:

`{REPO_URL}/compare/{DEFAULT_BRANCH}...{DeveloperFirstName}/{JiraTicketNumber}?expand=1`

**Present to the developer:**
> "Open this URL to create your PR:
> `{PR_URL}`
> 
> **PR title:** `{resolved_pr_title}`
> 
> I've prepared the PR description below - copy it into the PR form:
> 
> ---
> ## Summary
> {Brief description of what this PR does}
> 
> ## Jira Ticket
> [{JiraTicketNumber}](https://example.atlassian.net/browse/{JiraTicketNumber})
> 
> ## Changes Made
> - Code changes in {list affected areas}
> - Tests added/updated
> - AGENTS.md documentation updated
> - PRD regenerated
> 
> ## Testing
> - [x] All unit tests pass
> - [x] All integration tests pass
> - [ ] E2E tests pass (if applicable)
> - [ ] Manual testing completed
> 
> ## Checklist
> - [x] Code follows project patterns documented in AGENTS.md
> - [x] No conflicts with documented architecture
> - [x] Self-reviewed the code changes
> - [x] Developer approved changes before push"

### Step 12d: Confirm PR Created

**Ask the developer:**
> "Has the PR been created? Please confirm or paste the PR URL."

---

## STEP 13: Update Jira Ticket

**After the PR is created, update the Jira ticket status to reflect the work is ready for review.**

### Step 13a: Get Available Transitions

First, check what transitions are available for the ticket:

```
Call getTransitionsForJiraIssue with:
- issueIdOrKey: {JiraTicketNumber}
```

This will return a list of available status transitions.

### Step 13b: Transition to Ready for Peer Review

When `jira_transitions.on_pr_ready` is set in FactoryConfig, use that transition name. Otherwise look for common names:

Transition the ticket to "Ready for Peer Review" (or equivalent status):

```
Call transitionJiraIssue with:
- issueIdOrKey: {JiraTicketNumber}
- transitionId: {transition ID from Step 13a}
```

**Common transition names to look for:**
- "Ready for Peer Review"
- "Ready for Review"
- "In Review"
- "Code Review"

### Step 13c: Confirm Update

**Confirm with the developer:**
> "✅ Ticket {JiraTicketNumber} has been transitioned to 'Ready for Peer Review'."

**If the transition fails or the status name is different:**
> "⚠️ Could not transition ticket automatically. Available transitions: {list transitions}
> 
> Please manually update the ticket status in Jira to reflect that the PR is ready for review."

---

## Workflow Complete! 🎉

Summary of what was accomplished:
1. ✅ Identified developer ({DeveloperFirstName}) and selected Jira ticket: {JiraTicketNumber}
2. ✅ Analyzed requirements and acceptance criteria
3. ✅ Verified/created AGENTS.md files
4. ✅ Validated against AGENTS.md - no conflicts (or resolved)
5. ✅ Created feature branch: {DeveloperFirstName}/{JiraTicketNumber}
6. ✅ Implemented code changes
7. ✅ Added tests (unit/integration/e2e)
8. ✅ All tests passing
9. ✅ AGENTS.md documentation updated
10. ✅ PRD generated/updated
11. ✅ Developer reviewed and approved changes
12. ✅ Code committed and pushed
13. ✅ PR created
14. ✅ Jira ticket updated to Ready for Peer Review

**Next Steps:**
- Wait for code review from team
- Address any review feedback
- Merge when approved
