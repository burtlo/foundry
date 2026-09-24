# Jira board pick (Foundry intake)

Use when the user starts foundry **without** an issue key—same UX as the org ticket command’s sprint board, but **all JQL comes from FactoryConfig** (`jira.pick_list_jql` / `jira.project_key`).

**Kickoff UX (mandatory):** On board pick, the **first** thing the human sees is the resolved JQL and the **numbered ticket list**. Do **not** ask which app repo to implement in before showing the board. Resolve `{app_folder}` **after** the human picks a ticket **and** `getJiraIssue` (see [foundry SKILL.md](../../skills/foundry/SKILL.md) — Resolve implementation target).

**Atlassian connection:** Follow [atlassian-integration.md](./atlassian-integration.md) before any Jira API call — including **Step 0 MCP preflight** (plugin first; `mcp_auth` on `user-atlassian` only when plugin fails and legacy STATUS requires authentication).

**CRITICAL:** Do **not** copy JQL from legacy ticket commands, training data, or memory. Do **not** hardcode a project key (e.g. TICKET) in the agent session. The **only** source for board filter + project is **FactoryConfig** from the parent (`jira.pick_list_jql` + `jira.project_key`).

---

## Step 0 — Use parent FactoryConfig (mandatory, before MCP)

The parent already ran `foundry.py config get`. Do **not** read or parse `team-variables.md`.

1. Set `{project_key}` = FactoryConfig `jira.project_key` (required when `jira.enabled: true`).
2. Set `{pick_list_jql}` from FactoryConfig `jira.pick_list_jql` with every `{{project_key}}` replaced by `{project_key}` (parent may already have substituted).

**Example** (values come from the file, not from this doc):

```text
jira.project_key: TICKET
jira.pick_list_jql: |
  project = {{project_key}} AND sprint in openSprints() AND (...)

→ Resolved JQL passed to MCP:
  project = TICKET AND sprint in openSprints() AND (...)
```

3. **Pre-flight verification** (do not skip):
   - Resolved JQL must start with `project = {project_key}` (after substitution).
   - If it does not, **stop** and tell the human to fix `pick_list_jql` in `team-variables.md`.
4. **Show the human** the resolved JQL in one line before calling `searchJiraIssuesUsingJql` (transparency).

If `pick_list_jql` is empty, **stop**—do not invent a query.

---

## Step A — Current user

Resolve Atlassian connection per [atlassian-integration.md](./atlassian-integration.md), then call **`atlassianUserInfo`** (no args) on the working server. Store:

- `{developer_first_name}` — first token of display name (branch pattern)
- `{developer_account_id}` — account ID (assign on claim)

If all Atlassian sources fail, set `{atlassian_source}` = `manual` and ask human for first name once (for branch preview). Skip assign/claim until MCP is available.

---

## Step B — Sprint / board query

Use **`{pick_list_jql}`** from Step 0 only.

1. Resolve `cloudId` from `jira.cloud_id` or **`getAccessibleAtlassianResources`**.
2. Call **`searchJiraIssuesUsingJql`** with:
   - `jql`: **`{pick_list_jql}`** (already resolved; never a different query)
   - `maxResults`: `jira.pick_list_max_results` (default 50)
   - `fields`: include `summary`, `status`, `issuetype`, `priority`, `assignee`, `customfield_10026` or story points field if your board uses it
   - `responseContentFormat`: `markdown` when supported

### Error handling

If search fails after trying plugin and legacy MCP:

1. Show which sources were tried and why they failed.
2. **Do not** retry with legacy ticket-command JQL.
3. **Prompt human** for a Jira browse URL or issue key (see atlassian-integration.md Step 3).
4. Parse `{issue_key}`, fetch via `getJiraIssue` if a server becomes available, or build manual packet from pasted fields.
5. Jump to **Step D / D0** with manual/direct ticket (issue fetch + app resolve per SKILL).

If search succeeds but results include keys **outside** `{project_key}-` prefix, **stop** and show:
- The resolved JQL that was used
- The `pick_list_jql` template from `team-variables.md`
- Ask the human to fix variables—**do not** retry with legacy ticket-command JQL

---

## Step C — Present numbered board

Group issues by status (minimum):

- **To Do** — available to pick up
- **In Progress** — especially assignee = current user

Display:

```markdown
Hi {developer_first_name}! Tickets on the current board ({project_key}):

### To Do
1. PROJ-101 - Summary (Story, High)
2. ...

### In Progress (yours)
3. PROJ-99 - Summary (Task, Medium)
...

Reply with the **number** or **issue key** (e.g. PROJ-101).
```

**STOP and wait** for the human to select. Do not fetch full issue or run subagents until selection.

---

## Step D — After selection

Set `{issue_key}` from selection.

### D0 — Fetch issue (required before app routing)

Call **`getJiraIssue`** for `{issue_key}` with `responseContentFormat: markdown`. Store the response for D3 packet build and for ticket-hint app routing in D1.

### D1 — Resolve app repo (after pick + issue fetch)

Resolve `{app_folder}` per [foundry SKILL.md](../../skills/foundry/SKILL.md) (user prompt → **ticket hints from D0 issue** → single workspace app → `default_app_folder` → ask human only if still ambiguous).

Then:

### D2 — Claim ticket (when `jira.claim_on_pick: true` and `{atlassian_source}` is not `manual`)

If selected issue is **To Do**:

1. **`editJiraIssue`** — assignee `{developer_account_id}`
2. **`getTransitionsForJiraIssue`** then **`transitionJiraIssue`** to `jira_transitions.on_start` (e.g. "In Progress")
3. Confirm: "Ticket {issue_key} assigned to you and moved to In Progress."

If already In Progress and assigned to current user, confirm and continue.

If In Progress but assigned to someone else, warn and ask whether to continue.

### D3 — Full ticket contents

Use the **`getJiraIssue`** response from D0.

Extract and display **acceptance criteria** explicitly (from description or custom fields).

Build the **ticket packet** (include implementation target `{app_folder}` from D1):

```markdown
## Ticket packet
- Key: {issue_key}
- Summary: ...
- Issue type: {issuetype.name}
- Priority / Status
- Run mode: analysis | implementation
- Developer (branch): {resolved_branch_name}
- Description: ...
- Acceptance criteria:
  - [ ] AC1: ...
- Expected output: (Analysis tickets)
- Links: parent, dependencies
- Out of scope: ...
## Implementation target
- App folder: {app_folder}
```

If AC missing/vague and **`story_writer.enabled: false`**, stop and ask human to update Jira or paste AC.

### D3a — Run mode pivot (Step 0p)

After building the packet, parent runs **Step 0p** from foundry SKILL:

- If `analysis.enabled` and `issuetype.name` in `analysis.issue_types` → `Run mode: analysis`
- Else → `Run mode: implementation`

Tell the human which path will run.

### D3b — Story refinement (when `story_writer.enabled`)

After raw ticket packet + pivot:

- **Analysis path:** `story-writer` with `mode: analysis_deliverables` (DeliverableChecklist, StaleOrCompletedScope)
- **Implementation path:** `story-writer` with `mode: implementation` (gaps, proposed AC)

When **`story_writer.require_full_ac_presentation`** is `true` (default):

1. **Presentation turn:** follow **`templates.story_refinement_presentation`** — full AC/deliverables in chat, then **STOP**
2. **End the agent turn** — do not proceed to D4 in the same turn

When **`require_full_ac_presentation`** is `false`: use legacy inline Step 0a from SKILL.md (present + **ASK HUMAN** in one turn), then continue to factory Steps 1+ or A1+ after approval.

### D4 — Human approval

**Approval turn only** (never in the same turn as D3b story-writer presentation when `require_full_ac_presentation` is true):

**ASK HUMAN** (approval turn only — match **`story-refinement-presentation-step.md`** STOP line):

- **Implementation path:** **Approve** (suggested AC) | **Approve original** (Jira AC only) | **Edits** (paste revised AC) | **Update Jira first** | **Reject**. On Approve / Approve original / Edits → Steps 1–8.
- **Analysis path:** **Approve** | **Edits** (paste revised checklist) | **Update Jira first** | **Reject**. On Approve / Edits → Steps A1–A5.

---

## Kickoff phrases (board pick)

```text
Use foundry. Pick from the Jira board.
```

```text
Use foundry on Example.Api.
```

```text
/foundry
```

(Direct key bypasses this file: `Use foundry for PROJ-1234`.)
