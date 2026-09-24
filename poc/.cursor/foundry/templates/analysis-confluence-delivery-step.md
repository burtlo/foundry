# Factory analysis Confluence delivery

Used in **analysis.confluence** when `analysis.confluence.enabled` is `true`. Publishes the approved analysis to the team Confluence folder configured in team-variables. Does **not** post a Jira comment.

Use **FactoryConfig** from the parent for `analysis.confluence.*`, `jira.site_url`, and `jira.cloud_id`. Do not read `team-variables.md`. Resolve Atlassian connection per [atlassian-integration.md](../atlassian-integration.md).

**Gate:** Do **not** create or update Confluence content until the human explicitly approves Confluence delivery in this step — even if Step A2 report body was already approved.

---

## Variables

| Variable | Source |
|----------|--------|
| `{issue_key}` | Analysis ticket from packet |
| `{summary}` | Jira ticket summary |
| `{cloud_id}` | `jira.cloud_id` or `getAccessibleAtlassianResources` |
| `{site_url}` | `jira.site_url` |
| `{parent_folder_url}` | `analysis.confluence.parent_folder_url` |
| `{space_key}` | `analysis.confluence.space_key` (display / manual fallback) |
| `{space_id}` | `analysis.confluence.space_id` — **use for `createConfluencePage` MCP** (numeric ID) |
| `{parent_folder_id}` | `analysis.confluence.parent_folder_id` |
| `{title_pattern}` | `analysis.confluence.title_pattern` (default `{issue_key} {summary}`) |
| `{resolved_title}` | Substitute `{issue_key}` and `{summary}` into `{title_pattern}` — **same as Confluence page title and markdown H1** |
| `{resolved_title_filename}` | `{resolved_title}` with `\ / : * ? " < > |` replaced by `-`, collapsed spaces, trimmed — for `{markdown_path_pattern}` |
| `{ConfluencePageBody}` | Markdown from documentation-writer (Step A2); same as or expanded from `JiraCommentBody` |
| `{created_issue_keys}` | Follow-up stories from Step A4 (may be empty). A2 runs **before** A4 — merge keys here |
| `{app_folder}` | Target app repo for optional markdown archive |

Resolve page title: substitute `{issue_key}` and `{summary}` (Jira ticket **Summary** field) into `{title_pattern}` → `{resolved_title}`.

**Naming convention:** Match sibling pages under Jira Analysis Tickets — e.g. `TICKET-2343 SQL Transient Error Handling Analysis`, `TICKET-2416 Azure Database Data Sensitivity Levels`. Use the **exact Jira summary**; do not invent a shorter or alternate title.

For markdown archive path, substitute `{resolved_title_filename}` into `markdown_path_pattern` (default `Documentation/{resolved_title_filename}.md`).

---

## Step 1 — Prepare Confluence page body

Ensure `{ConfluencePageBody}` includes:

1. **H1 title:** `# {resolved_title}` — must match Confluence page title exactly
2. Link to Jira ticket: `[{issue_key}]({site_url}/browse/{issue_key})`
3. Analysis sections per `analysis.deliverable_sections`
4. **Follow-up stories (required merge):** A2 runs before A4, so `{ConfluencePageBody}` / `{JiraCommentBody}` will not contain created keys. **Before the Step 2 gate**, append or replace the section headed **`## Follow-up Stories`** (exact heading — match `documentation-writer.md`):

   When `{created_issue_keys}` is non-empty:

   ```markdown
   ## Follow-up Stories

   {for each key}- [{key}]({site_url}/browse/{key})
   ```

   When empty: omit the section, or use `## Follow-up Stories` with body `None`.
5. **Status** footer: analysis date, author, link to source repo markdown if saved

Apply the same follow-up block to `{JiraCommentBody}` so a Confluence skip still shows the keys in chat (A5a skip path presents once — A5c does not re-present).

Optionally add repo markdown archive when `analysis.confluence.save_markdown_to_app_repo` is `true`:

- Path: substitute `{resolved_title_filename}` into `analysis.confluence.markdown_path_pattern` under `{app_folder}` (default `Documentation/{resolved_title_filename}.md`)
- Write file **only after** human approves Confluence delivery in Step 2 — not before
- File content must use `# {resolved_title}` as the first heading

---

## Step 2 — Human approval gate (required)

Present to human:

```markdown
## Approve Confluence publish?

- **Jira ticket:** [{issue_key}]({site_url}/browse/{issue_key})
- **Parent folder:** {parent_folder_url}
- **Page title:** {resolved_title}
- **Space:** {space_key}

Preview the full page body below (or in saved markdown).

**Approve publishing this analysis to Confluence?** (yes / edit / skip / reject)
```

| Response | Action |
|----------|--------|
| **yes** | Continue to Step 3 |
| **edit** | Revise `{ConfluencePageBody}`; re-present gate |
| **skip** | Skip Confluence; set `{confluence_page_url}` empty; skip A5b; present the **merged** `{JiraCommentBody}` in chat only once (do not post to Jira); then A5c transition — **do not** re-present in A5c Step 1 |
| **reject** | Stop factory run; do not publish |

**Never** publish to Confluence without explicit **yes** in this step.

---

## Step 3 — Publish to Confluence

### 3a — MCP create (when available)

If Atlassian MCP exposes **`createConfluencePage`** (Atlassian plugin):

1. Create page under parent `{parent_folder_id}` in space `{space_id}` (prefer numeric `analysis.confluence.space_id`; resolve via `getConfluenceSpaces` if missing — **do not rely on `space_key` alone**)
2. Set title to `{resolved_title}`
3. Set body from `{ConfluencePageBody}` with `contentFormat: markdown`
4. Capture `{confluence_page_url}` from tool response (`_links.base` + `_links.webui`)
5. If the MCP create fails (error response, exception, or no URL returned), fall back to **3b manual publish** — do not treat a failed MCP call as a completed publish

### 3b — Manual publish (fallback)

When no create tool is available (current default):

1. Open parent folder: `{parent_folder_url}`
2. Create a new page with title `{resolved_title}`
3. Paste `{ConfluencePageBody}` as page content
4. Publish the page
5. Human provides `{confluence_page_url}` — confirm before continuing

**ASK HUMAN:** Confirm page URL when manual publish completes.

### 3c — Publish failed (both paths exhausted)

If MCP create failed **and** manual publish did not produce a confirmed `{confluence_page_url}` (human could not create the page, abandoned it, or provided no URL):

**ASK HUMAN** how to proceed:

| Response | Action |
|----------|--------|
| **retry** | Return to Step 3 |
| **skip** | Treat as Confluence skip: leave `{confluence_page_url}` empty, skip A5b, present the **merged** `{JiraCommentBody}` in chat only once (do not post to Jira), then A5c transition — **do not** re-present in A5c Step 1 |
| **stop** | Stop factory run; do not comment or transition |

**Never** call `addCommentToJiraIssue` on the analysis path. If Confluence was skipped, present the report in chat, then transition. Factory Jira comments exist only at implementation Step 8a before the PR.

---

## Step 4 — Hand off to transition

Set `{confluence_page_url}` when publish succeeded.

**Do not** post a Confluence link (or any other) comment on the Jira ticket.

Skip A5b. Proceed to **`analysis-delivery-steps.md`** (A5c).

---

## Order summary

| Order | Activity |
|-------|----------|
| A2 | documentation-writer produces `{ConfluencePageBody}` / `{JiraCommentBody}` |
| A2 gate | Human approves report content |
| A3–A4 | Optional follow-up stories |
| **A5a** | **This template** — approve Confluence publish → create page |
| A5b | skipped — no Jira comment (Step 8a before PR only) |
| A5c | Transition ticket + confirm (`analysis-delivery-steps.md`) |

No git branch, build, or PR on analysis path.
