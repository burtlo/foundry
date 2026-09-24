# Factory create Jira stories step

Used in **analysis.follow_up_create** when analysis findings require follow-up implementation work. Adapted from `branch-to-jira-task` Steps 3–5 (content review + `createJiraIssue`).

Read **FactoryConfig** from the parent for `jira.project_key`, `jira.cloud_id`, `jira.site_url`, and `analysis.follow_up_stories`. Do not read `team-variables.md`. Resolve Atlassian per [atlassian-integration.md](../atlassian-integration.md). Skip MCP creates when `{atlassian_source}` is `manual` — present drafts for human to create in Jira.

---

## Variables

- `{parent_issue_key}` — analysis ticket that spawned these stories
- `{cloud_id}` — `jira.cloud_id` or resolve via `getAccessibleAtlassianResources`
- `{project_key}` — `jira.project_key`
- `{site_url}` — `jira.site_url`
- `{issue_type}` — per draft from story-writer / engineer (Bug, Task, Story, Analysis, …); fall back to `analysis.follow_up_stories.issue_type` (default Task) only when a draft omits type
- `{labels}` — `analysis.follow_up_stories.labels`
- `{link_to_parent}` — `analysis.follow_up_stories.link_to_parent`
- `{developer_account_id}` — from `atlassianUserInfo` (optional reporter)

---

## Prerequisites

- Human approved **story-writer** `follow_up_stories` drafts (Step A3)
- `analysis.follow_up_stories.enabled` is `true`
- Skip this step entirely when no follow-up work is proposed or human declines

---

## Step 1 — Present drafts for review

For each draft from story-writer (`ProposedStory N`):

```markdown
### Proposed story {N}

**Summary:** {summary}
**Issue type:** {issue_type}
**Labels:** {labels or none}
**Parent link:** {parent_issue_key}

**Description:**
{description markdown}
```

**ASK HUMAN** for each draft:

- **Create as-is**
- **Edit title** — modify summary
- **Edit description** — modify body
- **Change issue type** — Bug / Task / Story / Analysis / other
- **Skip** — do not create this story
- **Cancel all** — stop without creating any

**WAIT** for developer input before calling MCP.

---

## Step 2 — Create approved issues

For each approved draft:

```
Call createJiraIssue with:
- cloudId: {cloud_id}
- projectKey: {project_key}
- issueTypeName: {approved issue type for this draft}
- summary: {approved summary}
- description: {approved description in Markdown}
- contentFormat: markdown
```

**IMPORTANT:** Do **not** set a sprint field — create in backlog only.

### Apply labels

When `{labels}` is non-empty:

```
Call editJiraIssue with:
- cloudId: {cloud_id}
- issueIdOrKey: {created issue key}
- fields: { "labels": {labels} }
```

### Link to parent analysis ticket

When `{link_to_parent}` is `true`:

```
Call createIssueLink with:
- cloudId: {cloud_id}
- inwardIssue: {created issue key}
- outwardIssue: {parent_issue_key}
- type: "Relates"
```

Use `getIssueLinkTypes` if Relates is unavailable; prefer Relates or Blocks per team convention.

Store each created key in `{created_issue_keys}`.

---

## Step 3 — Confirm creation

Present to human:

```markdown
## Follow-up stories created

| Key | Summary | Link |
|-----|---------|------|
| {key} | {summary} | [{key}]({site_url}/browse/{key}) |

**Parent analysis:** [{parent_issue_key}]({site_url}/browse/{parent_issue_key})
**Status:** Backlog (no sprint assigned)
```

Pass `{created_issue_keys}` to **A5a Step 1**, which **must** append them to `{ConfluencePageBody}` and `{JiraCommentBody}` before the Confluence gate. A5c chat skip uses that same merged body. Do **not** post them in a Jira comment.

---

## Description template (for story-writer drafts)

When story-writer does not supply full description, use this shape:

```markdown
## User Story

As a {role}, I want {action}, so that {benefit}.

## General Information

{Context from analysis findings}

**Spawned from:** [{parent_issue_key}]({site_url}/browse/{parent_issue_key})
**Repository:** {app_folder}

**Note:** Auto-generated from analysis follow-up. Review and adjust as needed.

## Acceptance Criteria

- [ ] {testable criterion 1}
- [ ] {testable criterion 2}
```
