# Jira comment gate (mandatory)

**The only factory step that may call `addCommentToJiraIssue` is implementation Step 8a**, after the Pre-Step-8 checklist and **before** `git commit` / `git push` / `gh pr create`.

Do **not** post Jira comments at A2, A5b, A5c, after the PR exists, during research/build/review, or from any subagent.

`jira.comments.require_human_approval` is **always `true`**. Do not treat any earlier factory gate as permission to post (A2 report draft, A5a Confluence, Step 6–7, story approval, or “proceed”).

---

## When this gate runs

| Condition | Action |
|-----------|--------|
| `{run_mode}` = `implementation`, Step 8a, `jira.enabled`, `jira.scope_comments.enabled`, **`PrExtrasRegister` non-empty** | Two-turn gate below, then post only after **Post** |
| Analysis path (no PR) | **Never** call `addCommentToJiraIssue`. Deliver via Confluence / chat. |
| Any other step | **Never** call `addCommentToJiraIssue` |

---

## Two-turn minimum (Step 8a only)

| Turn | Allowed | Forbidden |
|------|---------|-----------|
| **1 — Present** | Show the exact `{CommentBody}` in chat, then **STOP** | `addCommentToJiraIssue`, AskQuestion, commit, push, PR |
| **2 — Approve** | After the engineer replies **Post** / **Edit** / **Skip** | Posting on **Edit** or **Skip**; posting a body the engineer has not just approved |

Subagents must **never** call `addCommentToJiraIssue`. Only the parent agent posts, and only on turn 2 after **Post**.

---

## Turn 1 — Present (STOP)

Send one user-facing message with:

1. **Step 8a — PR extras** (before commit/PR).
2. Ticket `{issue_key}`.
3. The **exact** markdown that would be posted (`{CommentBody}` from `out-of-scope-jira-comment-step.md`).
4. This STOP line:

```markdown
---
**Review the proposed Jira comment above.** This is the only factory comment, and it is posted only before the PR. Reply on your next message with one of:
- **Post** — add this comment to {issue_key}, then continue to commit/PR
- **Edit** — tell me what to change; I will re-present and will not post until you say Post
- **Skip** — do not add a comment; continue to commit/PR
```

**End the turn.** Do not call MCP. Do not commit, push, or open a PR in this turn.

---

## Turn 2 — Engineer reply

| Reply | Action |
|-------|--------|
| **Post** | `addCommentToJiraIssue` with the last presented `{CommentBody}` (or manual paste when `{atlassian_source}` is `manual`), then continue to commit/PR |
| **Edit** | Revise `{CommentBody}`, go back to **Turn 1** (re-present + STOP). Do not post. |
| **Skip** | Do not post. Continue to commit/PR. |
| Anything else | Re-state the three options. Do not post. |

---

## After a successful Post

Confirm the comment was added, then continue **delivery-steps Step 3** (commit & push → PR). Do not post again after the PR exists.

One approval = one comment. A retry needs a new Turn 1 **before** the PR, not after.
