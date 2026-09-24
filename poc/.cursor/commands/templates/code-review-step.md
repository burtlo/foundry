# Developer Code Review

**CRITICAL: All changes must be reviewed by the developer BEFORE committing or pushing.**

---

## Show Summary of All Changes

Present a comprehensive summary to the developer:

> "📋 **Code Review - Summary of Changes**
> 
> **Jira Ticket:** {JiraTicketNumber}
> 
> **Files Modified/Created:**
> - {list each file with a brief description of changes}
> 
> **Code Changes:**
> - {summarize the key code changes}
> 
> **Tests Added/Modified:**
> - {list test files and what they test}
> 
> **Documentation Updated:**
> - {list AGENTS.md files updated}
> - PRD regenerated: {yes/no}
> 
> **Acceptance Criteria Status:**
> - [ ] {Criterion 1} - {Met/Not Met}
> - [ ] {Criterion 2} - {Met/Not Met}
> - [ ] *(continue for all criteria)*"

---

## Show Git Diff

Run and display the git diff for the developer to review:

```text
git diff --stat
git diff
```

---

## Request Review Approval

**Ask the developer:**

> "Please review the changes above. 
> 
> **Options:**
> - **Approve** - Proceed to commit and push
> - **Request changes** - Tell me what needs to be modified
> - **Show specific file** - I can show you any file in detail
> 
> Do you approve these changes?"

---

## Wait for Approval

**WAIT for explicit approval before proceeding to Commit and Push.**

---

## If Developer Requests Changes

1. Make the requested modifications
2. Re-run tests if code was changed
3. Update AGENTS.md/PRD if needed
4. Return to Step 10a to show updated summary

---

## Approval Received

Once the developer approves, proceed to Commit and Push.

