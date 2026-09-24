# Create Feature Branch

**Prerequisites:**
- `{DeveloperFirstName}` - Developer's first name (from Jira user info)
- `{JiraTicketNumber}` - The Jira ticket ID (e.g., TICKET-1234)
- `{factory_root}` and `{app_folder}` from the parent

---

## Create the branch

Parent (or this template) runs:

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" branch-name --pattern "{git.feature_branch_pattern}" --developer-first-name "{DeveloperFirstName}" --issue-key "{JiraTicketNumber}"
python "{factory_root}/.cursor/foundry/cli/foundry.py" branch create --repo "{app_folder}" --name "{branch from branch-name}"
```

Do not `git checkout origin/main`. The CLI resolves the short default-branch name.

---

## Branch Naming Standard

| Component | Example |
|-----------|---------|
| Format | `{DeveloperFirstName}/{JiraTicketNumber}` (or `git.feature_branch_pattern`) |
| Example | `Dan/TICKET-1234` |

---

## Confirmation

After successful branch creation, confirm:

> "✅ Created feature branch `{DeveloperFirstName}/{JiraTicketNumber}` from `{DEFAULT_BRANCH}`."

**Proceed directly to Implement Changes after branch creation.**
