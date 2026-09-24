# PR extras Jira comment (deliver.scope_comment)

**Primary purpose:** Document on the Jira ticket any work **included in the upcoming PR** that was **not called out** in the ticket description or acceptance criteria.

**Example:** A pinning-only ticket (TICKET-2402) whose PR also adds `.github/workflows/sync-prd.yml`, `AGENTS.md`, and generated PRD from mandatory factory Step 7.

---

## When to run

| Condition | Action |
|-----------|--------|
| `{run_mode}` = `implementation`, `jira.enabled` = `true`, **`jira.scope_comments.enabled`** = `true`, **`PrExtrasRegister` non-empty**, **before commit/PR** | Follow **`jira-comment-gate.md`**: present draft, **STOP**, `addCommentToJiraIssue` only after engineer **Post** |
| `{run_mode}` = `analysis` | **Never** comment — analysis has no PR |
| After `gh pr create` / PR already exists | **Never** comment |
| Register **empty** (PR diff matches ticket scope only) | Skip — no comment |
| **`jira.scope_comments.enabled`** = `false` or **`jira.enabled`** = `false` | **Auto-skip** Step 8a (register may still feed PR body when `include_in_pr_body`) |
| `{atlassian_source}` = `manual` | After **Post**, present comment body for human to paste |
| `jira.comments.require_human_approval` | Always `true` — never post in the same turn as the draft |

**Timing (required):** After **Pre-Step-8 gate checklist**, **before** `git commit`, `git push`, or `gh pr create`.

---

## `PrExtrasRegister` (parent maintains)

Initialize as an empty list after Step 0.

**Add an entry when ALL are true:**

1. The file or change **will be committed** in this PR (`git diff` / staged files vs `main`).
2. It is **not** described in the ticket summary, description, or approved acceptance criteria.
3. It is **intentional** work (not an accidental edit to revert).

**How to populate (parent, before Step 8a):**

1. Run `git diff main --name-only` and list staged/untracked files intended for the PR.
2. Compare each path to the **approved ticket packet** and **technical brief in-scope** section.
3. Merge rows from **documentation-writer** `DocChangeReport` → **`IncludedInPrOutsideTicket`** (required when Step 7 created files).
4. Merge rows from **devops-builder** / **builders** when workflow or code changes exceed ticket AC (and human approved keeping them).
5. Merge explicit human additions ("keep sync-prd; document on Jira").

**Typical entries (factory Step 7 on a narrow ticket):**

| File / area | Purpose | Why not in ticket |
|-------------|---------|-------------------|
| `.github/workflows/sync-prd.yml` | PRD sync caller to the factory documentation repo | Factory Step 7d — not in pinning AC |
| `AGENTS.md` | Root agent / CI documentation | Factory Step 7 |
| `{entry-point}/AGENTS.md` | Entry-point documentation | Factory Step 7 |
| `Documentation/prd-*-generated.md` | Generated PRD | Factory Step 7 |
| `Documentation/prd-generator-prompt.md` | PRD generator prompt | Factory Step 7 |

Each register row: `| {path or area} | {one-line purpose} | {why not in ticket — e.g. factory Step 7} |`

**Do not add:**

- Files that **are** the ticket work (e.g. `ci-build.yml` pin on a pinning ticket).
- Work **not** in the PR (use PR description or a separate follow-up ticket instead — see optional deferred note below).

---

## Comment body template (required shape)

Substitute `{issue_key}`, `{branch}`, `{in_scope_summary}`, `{developer_display_name}`.

```markdown
## PR includes work not called out in this ticket

**Ticket:** {issue_key}
**Branch:** {branch}
**PR:** Pending — commit/PR will follow this comment

The upcoming PR includes the following changes that were **not** in the ticket description or acceptance criteria:

| File / area | Purpose | Notes |
|-------------|---------|-------|
| `.github/workflows/sync-prd.yml` | PRD sync caller workflow | implement.documentation |
| … | … | … |

**In scope for this ticket (also in PR):** {in_scope_summary}

These additions are intentional (org Foundry / team policy). Reviewers: please treat the table above as scope documentation, not scope creep to revert without discussion.

— Posted via foundry on behalf of {developer_display_name}
```

When `jira.scope_comments.include_in_pr_body` is `true`, add the same table under **`## PR work not in ticket`** in the PR body.

---

## Optional: deferred items (`document_deferred: false` default)

When `jira.scope_comments.document_deferred` is `true`, append a second section listing work **identified but not in the PR**. Default is **false** — most teams only want the "extras in PR" comment.

---

## Step 1 — Build register and draft

1. Finalize **`PrExtrasRegister`** from diff + subagent reports.
2. If empty → skip Step 8a.
3. Build `{PrExtrasCommentBody}` from template above.

Set `{CommentBody}` = `{PrExtrasCommentBody}` and follow **`jira-comment-gate.md`** (`templates.jira_comment_gate`) **end to end**. Prefix the Turn 1 message with:

> **PR extras Jira comment (Step 8a — before commit/PR)**
>
> The PR includes {N} item(s) not called out in the ticket.

**STOP** after presenting. Do not commit, push, or open a PR in the presentation turn.

---

## Step 2 — Gate outcomes (do not post again)

`jira-comment-gate.md` owns **Post** / **Edit** / **Skip** and the single `addCommentToJiraIssue` call (or manual paste). **Do not** invoke `addCommentToJiraIssue` again in this step.

| Gate outcome | Action |
|--------------|--------|
| **Post** | Gate already posted — continue to Step 3 |
| **Skip** | No comment — continue to Step 3 |
| **Edit** | Gate re-presents — remain in Step 8a |

---

## Step 3 — Report

- **pr_extras_comment** — `posted` | `skipped` | `manual_paste` | `not_needed`
- **pr_extras_count** — rows in register

Then proceed to **delivery-steps Step 3** (commit & push).
