# Atlassian integration (Foundry)

Jira API calls in foundry use a **three-step fallback**. Parent agents must follow this order before every `atlassianUserInfo`, `searchJiraIssuesUsingJql`, `getJiraIssue`, `transitionJiraIssue`, or `addCommentToJiraIssue` call.

**Config:** `atlassian.*` keys in [team-variables.md](./team-variables.md). Tool names are the same across plugin and legacy MCP.

---

## Step 0 — MCP preflight (mandatory before giving up)

**Do not** conclude Atlassian is unavailable from a single `CallMcpTool` error ("MCP server does not exist"). Cursor may list tool descriptors on disk while the runtime server is unauthenticated or errored.

1. Inspect MCP status files under the workspace project cache (paths like `mcps/plugin-atlassian-atlassian/STATUS.md` and `mcps/user-atlassian/STATUS.md`).
2. **Plugin first (Step 1):** For each id in `{plugin_mcp_servers}` (or `{plugin_mcp_server}` if the list is empty), skip any id whose STATUS is **errored**. Call **`atlassianUserInfo`** on the first non-errored plugin id. Success → set `{atlassian_source}` = `plugin`, set `{working_mcp_server}` to that id, and use it for all Jira tools in the session.
3. **Legacy fallback (Step 2):** If all plugin ids fail or are errored, and a legacy id in `atlassian.legacy_mcp_servers` (e.g. **`user-atlassian`**) has STATUS **needs authentication**, call **`mcp_auth`** with `{}` on that server via `CallMcpTool` before any Jira tool. This triggers OAuth in the browser; wait for success. The HTTP Rovo endpoint is the same integration the plugin uses.
4. Call **`atlassianUserInfo`** on each legacy server in `atlassian.legacy_mcp_servers` order until one responds. Success → set `{atlassian_source}` = `legacy_mcp`, set `{working_mcp_server}` to that id. Only if both plugin and legacy fail after preflight → fall through to Step 3 manual mode.

**Working server ids (try in order after STATUS check):**

| Order | Server id | Notes |
|-------|-----------|-------|
| 1 | `plugin-atlassian-atlassian` | Plugin MCP (default); use when STATUS is not errored |
| 2 | `user-atlassian` | Legacy HTTP MCP from `~/.cursor/mcp.json` key `atlassian`; call `mcp_auth` when STATUS requires it |

Set `{working_mcp_server}` to the id that answered `atlassianUserInfo`. Use it for **all** Jira tools in the session. Set `{atlassian_source}` to `plugin` or `legacy_mcp` according to which tier succeeded — do not label a healthy plugin session as `legacy_mcp`.

---

## Fallback order

| Step | Source | When to use |
|------|--------|-------------|
| **1** | **Atlassian Cursor plugin** | Default — install from [Cursor Marketplace → Atlassian](https://cursor.com/marketplace/atlassian) |
| **2** | **Legacy Atlassian MCP** | Plugin unavailable, not authenticated, or tool call fails |
| **3** | **Manual Jira URL** | Both integrations fail — human provides browse URL or pastes ticket fields |

Record `{atlassian_source}` in the ticket packet: `plugin` | `legacy_mcp` | `manual`.

---

## Step 1 — Atlassian Cursor plugin (preferred)

The org **Atlassian** marketplace plugin bundles MCP tools and skills. When installed **and MCP is enabled for the workspace**, tools are exposed under:

| Setting | Default |
|---------|---------|
| `{plugin_mcp_server}` | `plugin-atlassian-atlassian` (from `atlassian.plugin_mcp_server` in team-variables) |
| `{plugin_mcp_servers}` | Ordered list to try (defaults to `[plugin-atlassian-atlassian]`) |

**Verify:** Complete **Step 0 preflight** first. For each id in `{plugin_mcp_servers}` (or `{plugin_mcp_server}` if the list is empty), call `atlassianUserInfo` with no arguments via `CallMcpTool`. First success → set `{atlassian_source}` = `plugin`, set `{working_mcp_server}` to that id, and use it for all Jira tools in the session. If plugin ids fail or STATUS is errored, continue to Step 2 — do not stop at "server does not exist".

**Setup (one-time per developer):**

1. Cursor → Extensions / Marketplace → install **Atlassian** plugin
2. **Cursor → Settings → MCP** → enable **atlassian** / **plugin-atlassian-atlassian** for this workspace (green/connected)
3. Complete OAuth when prompted (browser flow)
4. Confirm `atlassianUserInfo` returns your display name

**Installed but MCP missing in this workspace?** The plugin can be installed globally while its MCP server is disabled per workspace. Open **Settings → MCP**, toggle the Atlassian server on, then start a **new Agent chat**. Other workspaces (e.g. KT-IoT-Sonorus) may already show `plugin-atlassian-atlassian` in the MCP list — enable it the same way here.

Plugin MCP endpoint (managed by plugin): `https://mcp.atlassian.com/v1/mcp/authv2`

---

## Step 2 — Legacy Atlassian MCP (fallback)

If Step 1 fails (server not listed, auth error, timeout), try each server in `atlassian.legacy_mcp_servers` from team-variables, in order:

| Runtime server id | Source |
|-------------------|--------|
| `user-atlassian` | `%USERPROFILE%\.cursor\mcp.json` (Windows) or `~/.cursor/mcp.json` (macOS/Linux) key `atlassian` (recommended HTTP fallback) |

**Recommended user MCP config** (foundry ships with this in org setup; add to `%USERPROFILE%\.cursor\mcp.json` or `~/.cursor/mcp.json` if missing):

```json
{
  "mcpServers": {
    "atlassian": {
      "url": "https://mcp.atlassian.com/v1/mcp/authv2"
    }
  }
}
```

Cursor exposes this as runtime id **`user-atlassian`** (prefix `user-` + config key). That id must appear in `atlassian.legacy_mcp_servers` — not the raw config key `atlassian`.

After adding or editing `mcp.json`, reload MCP (**Settings → MCP** → refresh) or restart Cursor, complete OAuth once, then retry in a **new Agent chat**.

**Verify:** Complete **Step 0 preflight** (`mcp_auth` on `user-atlassian` when STATUS requires it). Call `atlassianUserInfo` on the first legacy server that responds. Success → set `{atlassian_source}` = `legacy_mcp`, set `{working_mcp_server}` to that id, and use **that** server for all subsequent Jira tools in the session.

**Do not** mix servers mid-run — pick one working source and stick with it.

---

## Step 3 — Manual Jira URL (last resort)

When **both** plugin and legacy MCP fail:

### Board pick (no issue key yet)

1. Tell the human which sources were tried and why they failed (not installed, not authenticated, network, etc.).
2. **Prompt once:**

   > Atlassian integration is unavailable. Paste a **Jira browse URL** for the ticket to work on (e.g. `https://yoursite.atlassian.net/browse/PROJECT-123`), or reply with an **issue key** (e.g. `TICKET-1234`).

3. Parse `{issue_key}` from URL or key text (see patterns below).
4. Validate against `jira.issue_key_pattern` when set.
5. Set `{atlassian_source}` = `manual`.
6. **Retry `getJiraIssue`** once on any server that became available; if still failing, ask human to paste:
   - Summary
   - Description
   - Acceptance criteria (numbered list)
   - Issue type (Story / Task / Analysis / Bug)
7. Build **manual ticket packet** from pasted content. Mark fields sourced from human paste.
8. For `{developer_first_name}`: ask human once (do not guess from git config).
9. **Skip** board pick, claim, and Jira transitions until MCP works again — note in packet: `Jira write operations deferred (manual mode)`.

### Direct key or URL already in user message

1. Parse `{issue_key}` from message or URL.
2. Run Steps 1–2 once; if both fail, set `manual` and prompt for pasted ticket fields as above.
3. Continue factory with manual packet — story-writer and research still run.

### Analysis / delivery paths in manual mode

- Steps A5 (Confluence / transition) and Step 8 Jira transition: **stop** before write; present status to human. Jira **comments** are Step 8a only (before PR) and require **Post** per `jira-comment-gate.md`. Analysis path must not comment.

---

## URL and key parsing

Accept common Atlassian Cloud browse URLs:

```text
https://{site}/browse/{issue_key}
https://{site}/jira/software/projects/{project}/issues/{issue_key}
https://{site}/jira/browse/{issue_key}
```

`{issue_key}` = final path segment matching `jira.issue_key_pattern` (e.g. `^TICKET-\d+$`).

Also accept bare keys in chat: `TICKET-1234`, `PROJ-1234`.

---

## Shared Jira tools (plugin and legacy)

| Tool | Foundry use |
|------|---------------------|
| `atlassianUserInfo` | Developer identity, branch naming |
| `getAccessibleAtlassianResources` | Resolve `cloudId` when `jira.cloud_id` empty |
| `searchJiraIssuesUsingJql` | Board pick (Step B) |
| `getJiraIssue` | Ticket packet |
| `editJiraIssue` | Claim on pick |
| `getTransitionsForJiraIssue` | Claim / delivery transitions |
| `transitionJiraIssue` | In Progress, PR ready, Done |
| `addCommentToJiraIssue` | **Implementation Step 8a only** (`PrExtrasRegister` — before commit/PR). Never analysis A2/A5. Never after the PR exists. Requires engineer **Post**. |
| `createJiraIssue` | Follow-up stories |

**cloudId:** Prefer `jira.cloud_id` or `jira.site_url` from team-variables when set — avoids extra `getAccessibleAtlassianResources` calls (see Atlassian plugin AGENTS.md guidance).

---

## Developer identity

When `git.developer_first_name_source` is `atlassian` or `atlassian_mcp` (legacy alias):

1. Call `atlassianUserInfo` via resolved `{atlassian_source}` server.
2. `{developer_first_name}` = first whitespace-delimited token of display name.
3. If all sources fail → ask human once.

---

## Error messages (human-facing)

Keep failures actionable:

```markdown
**Atlassian integration unavailable**

Tried:
1. Atlassian Cursor plugin (`plugin-atlassian-atlassian`) — {reason}
2. Legacy MCP (`user-atlassian` from `~/.cursor/mcp.json`) — {reason}

**Next steps:**
- **Settings → MCP** → enable **plugin-atlassian-atlassian** (plugin) or **user-atlassian** (HTTP fallback), then start a new Agent chat
- Or paste a Jira browse URL / issue key to continue in manual mode
- Install/authenticate the [Atlassian Cursor plugin](https://cursor.com/marketplace/atlassian) if not installed
```

---

## Kickoff (no Jira MCP required to start)

Factory can always start; MCP is resolved at Step 0:

```text
Use foundry. Pick from the Jira board.
```
