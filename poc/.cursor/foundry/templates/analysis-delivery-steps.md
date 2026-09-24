# Factory analysis delivery steps

Used in **analysis.deliver** after Confluence publish or skip. Analysis path **does not** post Jira comments (`addCommentToJiraIssue` is implementation **Step 8a only**, before the PR).

When `analysis.confluence.enabled` is `true`, run **A5a Confluence**, skip A5b, then complete transition below.

Use **FactoryConfig** from the parent for `analysis.confluence`, `analysis.jira_transitions`, `jira.site_url`, and `jira.cloud_id`. Do not read `team-variables.md`. Resolve Atlassian connection per [atlassian-integration.md](../atlassian-integration.md).

---

## Step 0 — Prior steps (when Confluence enabled)

| Step | Template | Outcome |
|------|----------|---------|
| A5a | `analysis-confluence-delivery-step.md` | `{confluence_page_url}` set after successful publish, or empty after skip |
| A5b | skipped | No Jira comment on analysis tickets |

If human **rejected** Confluence in A5a, stop — do not comment or transition.

If human **skipped** Confluence — or publish failed and the human chose **skip** at the A5a Step 3c failure gate — A5a already merged follow-ups and presented `{JiraCommentBody}` in chat. **Do not** merge or present again in A5c Step 1.

---

## Variables

- `{issue_key}` — analysis ticket from packet
- `{site_url}` — `jira.site_url` (e.g. `https://example.atlassian.net`)
- `{cloud_id}` — `jira.cloud_id` or resolve via `getAccessibleAtlassianResources`
- `{JiraCommentBody}` — markdown from documentation-writer (chat/Confluence only — never posted to Jira)
- `{confluence_page_url}` — from A5a (may be empty)
- `{created_issue_keys}` — follow-up stories from Step A4 (may be empty)
- `{on_complete}` — `analysis.jira_transitions.on_complete` or `jira_transitions.on_analysis_complete`

---

## Step 1 — Chat-only report when Confluence disabled

Run **only** when `analysis.confluence.enabled` is **`false`** (A5a does not run).

1. Merge `{created_issue_keys}` into `{JiraCommentBody}` the same way as A5a Step 1 (append or replace **`## Follow-up Stories`** with `{site_url}/browse/{key}` links). A2 ran before A4, so the A2 draft will not already have those keys.
2. Present the merged `{JiraCommentBody}` in chat once. **Do not post it to Jira.**

When `analysis.confluence.enabled` is **`true`** (published or skipped in A5a), **skip this step** — A5a already merged follow-ups; on skip, A5a already presented the chat report.

---

## Step 2 — Transition analysis ticket

When `{on_complete}` is set and `{atlassian_source}` is not `manual`:

1. `getTransitionsForJiraIssue` for `{issue_key}`
2. Find transition matching `{on_complete}` (e.g. Ready for Peer Review)
3. `transitionJiraIssue` with matching transition id

If transition is unavailable, tell the human the current status and available transitions — do not guess.

When `{atlassian_source}` is `manual`, ask human to move the ticket to `{on_complete}` in Jira UI.

---

## Step 3 — Confirm completion

Present to human:

```markdown
## Analysis delivered

- **Ticket:** [{issue_key}]({site_url}/browse/{issue_key})
- **Confluence:** {confluence_page_url or skipped}
- **Jira comment:** none (factory comments are Step 8a before PR only)
- **Status:** {on_complete or unchanged}
- **Follow-up stories:** {created_issue_keys or none}
```

**ASK HUMAN:** Confirm analysis is complete.

---

## Order summary

| Order | Activity |
|-------|----------|
| Earlier | Step A1–A4 research, report, optional story drafts |
| Step A5a | analysis-confluence-delivery-step.md (when `analysis.confluence.enabled`) |
| Step A5b | skipped — no Jira comment |
| Step A5c | **This template** — transition + confirm |

No branch, commit, push, PR, or Jira comment on this path.
