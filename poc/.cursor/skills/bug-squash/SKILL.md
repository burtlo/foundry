---
name: bug-squash
description: >-
  Orchestrates production bug triage: Azure Monitor MCP for top errors,
  codebase-researcher for root cause, backend/client builders in propose_fix
  to pressure-test the fix, then story-writer for gated Jira receipts.
  Default lookback 7 days (overridable). Engineer approves at Gate 0/1/2.
  Use when the user says bug-squash, bug squash, squash bugs, top errors,
  production failures, or Azure Monitor exception triage for any app/solution.
disable-model-invocation: true
---

# Bug squash

Orchestrator skill. **You are the parent agent.** Delegate focused work to subagents; do not inline their jobs in one bloated context.

**Reusable across any solution.** The skill is not tied to a single app. Each run targets **one** `{app_folder}` + `{environment}` and whatever Azure Monitor logs that app uses. App-specific names live only in `bug_squash.targets` (or are discovered and confirmed at kickoff) — never hardcode an app, workspace, or role name in this skill’s logic.

Find the most common Azure Monitor errors for the chosen app, pressure-test a fix proposal with builders, and optionally create Jira issues as receipts. **Azure Monitor MCP** is the primary query path; Azure CLI is the fallback.

**You are the parent agent.** Do not create Jira issues or change code until the engineer explicitly approves. Builders run in **`propose_fix` only** — no file edits from this skill.

## Defaults (overridable)

| Setting | Default | Override |
|---------|---------|----------|
| Lookback | **7 days** (`168` hours) | User prompt: `last 24h`, `lookback 3d`, `hours: 48` |
| Top N error groups | `10` | User prompt or `bug_squash.top_n` |
| Environment | **prod** | User prompt (`dev` / `qa` / `prod`) or `bug_squash.default_environment` |
| Builder critique | **required** (`require_builder_critique: true`) | Engineer may skip per finding |
| Max parallel researchers | `3` | `bug_squash.max_parallel_researchers` |
| Issue type | **Per finding** (see below) | Engineer override at Gate 1 or 2 |

Resolve lookback once at kickoff:

1. User-supplied hours/days → `{lookback_hours}`
2. Else `bug_squash.default_lookback_hours` from FactoryConfig
3. Else **168** (7 days)

Resolve environment once at kickoff:

1. User-supplied `dev` / `qa` / `prod` → `{environment}`
2. Else `bug_squash.default_environment` from FactoryConfig
3. Else **prod**

Do **not** infer environment from the current `az account` subscription name. If the active subscription does not match `{environment}`, switch (or ask the engineer to switch) to the correct subscription before querying.

State the resolved lookback and environment in the first status line before querying.

## Prerequisites

1. Resolve `{factory_root}` (same order as [factory-bootstrap](../factory-bootstrap/SKILL.md)). Load **FactoryConfig**:

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" config get --factory-root "{factory_root}" --role parent --app-folder "{app_folder}"
```

Use `jira.*`, `atlassian.*`, `bug_squash.*`, `builders.*`, `workspace.*` from that JSON. Pass a role-scoped FactoryConfig on every subagent launch. **Do not** tell subagents to read `team-variables.md`.
2. Resolve `{app_folder}` and telemetry per **Resolve app + telemetry target** (never assume a default product beyond `default_app_folder` when the engineer did not name an app).
3. Read `{app_folder}/AGENTS.md` for app context and telemetry hints.
4. **Ensure Azure auth** (do not ask the engineer to run login themselves):

   | Check | Action |
   |-------|--------|
   | `az account show` succeeds **and** Monitor MCP can list/query | Continue |
   | CLI or MCP returns unauthorized / expired token / `AADSTS70043` / `CredentialUnavailableException` | **Auto-login** (below) |
   | Active subscription does not match `{environment}` | `az account set` to the correct subscription (do not infer env from the current sub name) |

   ### Auto-login (mandatory when unauthorized)

   Use `bug_squash.azure_tenant`, `bug_squash.azure_login_scope`, and `bug_squash.azure_subscriptions` from FactoryConfig.

   1. Run device-code login in the agent shell (engineer completes browser step):

      ```bash
      az login --tenant "{bug_squash.azure_tenant}" --scope "{bug_squash.azure_login_scope}" --use-device-code
      ```

      If a prior session is half-broken, `az logout` first, then the same `az login`.

   2. Surface the **device code URL + code** to the engineer immediately and wait for the login command to finish (do not proceed with Monitor queries while login is in flight).
   3. After success, `az account set` using `bug_squash.azure_subscriptions[{environment}]` (name or GUID). Re-check `az account show`.
   4. Only if auto-login fails after the engineer completes the browser step (or they cancel) — stop and report the error. Do **not** skip auth and invent telemetry.

   Prefer `--use-device-code` over browser-broker login in agent terminals (macOS broker / non-main-thread failures are common).

## Query path (prefer Monitor MCP)

**Primary:** Azure MCP `plugin-azure-azure` → tool `monitor`

| Need | Command |
|------|---------|
| List workspaces | `monitor_workspace_list` |
| List tables | `monitor_table_list` / `monitor_table_type_list` |
| Workspace-wide KQL | `monitor_workspace_log_query` |
| Single resource KQL | `monitor_resource_log_query` |

**Do not** use `applicationinsights` MCP for log/exception queries (component inventory only).

**Fallback CLI** when MCP is unavailable:

```bash
az monitor app-insights query --app {app_insights_name} --resource-group {rg} --analytics-query "{kql}" --offset {lookback_hours}h
# or Log Analytics:
az monitor log-analytics query --workspace {workspace_id} --analytics-query "{kql}" --timespan PT{lookback_hours}H
```

KQL templates: [kql-queries.md](kql-queries.md).

## Resolve app + telemetry target

### App (`{app_folder}`)

Order:

1. User names an app / repo / folder in the prompt
2. Else `workspace.default_app_folder` from FactoryConfig
3. Else if exactly one non-org folder is open in the workspace → use it
4. Else **ASK HUMAN** — list `workspace.app_folders` (and any other open roots); do not assume a favorite app

Read `{app_folder}/AGENTS.md` (and nested entry-point AGENTS.md if present) for hosting, App Insights notes, and resource naming hints. Treat AGENTS.md as **hints**, not hard-coded truth — confirm against Azure when unsure.

### Telemetry (`{workspace}` / App Insights / scope)

Order:

1. User names App Insights component, resource ID, Log Analytics workspace, or KQL scope
2. `bug_squash.targets[{app_folder}][{environment}]` when present
3. Discover via Azure MCP / `az` (list App Insights + workspaces in likely RGs from AGENTS.md / naming patterns) and **ASK HUMAN** to confirm before the first top-errors query

**Target schema** (per app + env; all fields optional except one of workspace / app_insights / resource_id):

| Field | Purpose |
|-------|---------|
| `workspace` | Log Analytics workspace name or customer ID |
| `resource_group` | RG for the workspace (when needed for table list) |
| `app_insights` | App Insights component name (dedicated or shared) |
| `app_insights_resource_group` | RG for the component |
| `resource_id` | Full Azure resource ID (prefer for `monitor_resource_log_query`) |
| `table` | Override default table (`AppExceptions` / `exceptions`) |
| `role_filters` | List of `AppRoleName` / cloud role substrings to keep when the workspace is **shared** |
| `resource_id_filters` | Optional `_ResourceId` / Function App name substrings when role alone is ambiguous |

**Shared vs dedicated telemetry:**

- If the app has a **dedicated** App Insights component → prefer querying that component (resource log query or classic `az monitor app-insights query`) so results are already scoped.
- If the app shares a **workspace or App Insights** with other services → you **must** apply `role_filters` / `resource_id_filters` (or an engineer-approved KQL `where`) so top errors are for **this** app only. Never present a shared-workspace top-10 as if it were a single product.
- When filters are unknown: list distinct `AppRoleName` (or classic `cloud_RoleName`) for the lookback, show the engineer the candidates, and **ASK HUMAN** which roles belong to `{app_folder}` before aggregating.

**Persist discoveries:** After the engineer confirms a new target (and role filters), offer to write it into `bug_squash.targets[{app_folder}][{environment}]` in team-variables so the next run for that app skips rediscovery. Do not invent entries for apps that were not confirmed.

Record for the run: `{app_folder}`, `{environment}`, `{lookback_hours}`, `{workspace}` and/or `{resource_id}` / `{app_insights}`, `{table}`, `{role_filters}` (if any).

State in the first status line: **app · env · lookback · telemetry identity** (workspace or AI name + whether scoped by role).

---

## Workflow checklist

```
Bug Squash Progress:
- [ ] 1. Resolve app, env, lookback, telemetry target
- [ ] 2. Query top errors (Monitor MCP)
- [ ] 3. GATE 0 — engineer picks error groups to investigate
- [ ] 4. codebase-researcher (bug_triage) per selected finding
- [ ] 5. backend/client builder (propose_fix) — refine ProposedFix
- [ ] 6. GATE 1 — engineer reviews refined findings + fixes
- [ ] 7. story-writer drafts Jira receipts (approved findings only)
- [ ] 8. GATE 2 — engineer approves each story (type/summary/body)
- [ ] 9. Create approved Jira issues (receipts)
- [ ] 10. Summarize keys + links; stop (no auto-implement)
```

---

## Step 1 — Query top errors

Run the **Top exceptions by type/message** query from [kql-queries.md](kql-queries.md) with `{lookback_hours}`, `{top_n}`, and the run’s **app scope filter** (from `role_filters` / confirmed roles — see kql-queries “App scope”).

If the scoped query returns empty but the unscoped workspace has data, re-check role filters with the engineer (wrong role name is the usual cause) — do not silently widen to the whole shared workspace.

Then for the top groups (or engineer-selected subset after Gate 0), run a **sample stack** query (1–3 rows each), still with the same app scope. At Gate 0 you may show counts first, then fetch stacks only for Investigate-selected groups.

Present a compact table:

| Rank | Count | Exception / problemId | Sample message | First seen | Last seen |
|------|-------|----------------------|----------------|------------|-----------|

Do not dump raw KQL result blobs into chat — summarize.

## Step 2 — GATE 0 (mandatory)

Present the top-error table.

**ASK HUMAN** for each group (or allow “investigate all top N”):

- **Investigate** — launch researcher (+ builder unless skipped)
- **Skip** — noise / known / out of scope
- **Cancel squash** — stop entirely

Optional per finding: **Skip builder** (only when `require_builder_critique` is false or engineer explicitly opts out).

**WAIT.** Do not launch `codebase-researcher` until the engineer responds.

## Step 3 — codebase-researcher (`bug_triage`)

For each **Investigate**-selected finding, launch subagent **`codebase-researcher`** with `mode: bug_triage`.

Pass **only**:

- Role-scoped **FactoryConfig** (`config get --role codebase-researcher`) and **FactoryRunState**
- Exception type, sample message, sample stack frames
- Counts, first/last seen, sample OperationId / problemId
- `{lookback_hours}`, `{environment}`, `{app_folder}`
- Telemetry identity (workspace / resource / role when known)

Cap parallel launches at `bug_squash.max_parallel_researchers` (default **3**).

Parent merges outputs. Do **not** invent a final fix in the parent — use researcher draft only as input to the builder.

## Step 4 — Builder `propose_fix` (required by default)

When `bug_squash.require_builder_critique` is **true** (default), launch a builder for each researcher packet **before** Gate 1.

### Route backend vs client

1. Match researcher `RelevantFiles` + stack frames to the app-manifest snapshot `builders.routes` (highest priority wins; unmatched paths use `default_owner`).
2. Launch **`backend-builder`** and/or **`client-builder`** with `mode: propose_fix`. Include role-scoped **FactoryConfig** (`config get --role backend-builder` / `client-builder`) and **FactoryRunState**.
3. If ambiguous: prefer **backend** for API / Functions / SQL / Event Hub stacks; **client** for Blazor / UI stacks; ask engineer only when both look equally likely.
4. When both layers are implicated, run backend then client (or parallel only if independent).

Pass: full researcher `bug_triage` packet + Azure evidence summary.

**Hard rule:** builders must **not** edit files in this skill. If a builder starts implementing, stop and re-launch with explicit `mode: propose_fix` and “read-only; no file edits.”

**Hard rule:** never put a researcher draft fix into Jira without a builder pass unless the engineer explicitly skipped builder for that finding.

Merge into a findings board for Gate 1:

| Field | Source |
|-------|--------|
| Root cause | researcher |
| **RefinedProposedFix** | builder |
| RejectedApproaches | builder (show why naive fixes were dropped) |
| Severity / issue type | researcher, adjusted if builder disagrees |
| Confidence | builder |

## Step 5 — GATE 1 (mandatory)

Present findings + **refined** proposed fixes + recommended issue types + RejectedApproaches.

**ASK HUMAN** for each finding:

- **Ticket** — include in Jira receipt set (optionally override issue type)
- **Investigate more** — deepen query/code before ticketing
- **Skip** — noise / known / out of scope
- **Cancel squash** — stop entirely

**WAIT.** Do not launch story-writer or create Jira until the engineer responds.

Also confirm: create Jira receipts now? (default yes if `bug_squash.create_jira_receipts: true`)

### Issue type from findings (not a fixed default)

Recommend **one** Jira issue type per finding:

| Finding shape | Prefer |
|---------------|--------|
| Clear defect in existing behavior / regression | **Bug** |
| Config, ops, monitoring, or small remediation with known steps | **Task** |
| New capability or product-facing change required | **Story** |
| Root cause unclear; research needed before fix | **Analysis** (or Spike if that type exists) |

State the recommendation and rationale. The engineer may override at Gate 1 or Gate 2.

## Step 6 — story-writer drafts

For **Ticket**-approved findings only, launch **story-writer** with:

- Role-scoped **FactoryConfig** (`config get --role story-writer`) and **FactoryRunState**
- `mode: follow_up_stories`
- Inputs: Azure evidence + **builder `RefinedProposedFix`** (+ `RejectedApproaches`, `SuggestedAcceptanceCriteria`)
- Fall back to researcher draft ProposedFix **only** if builder was skipped for that finding
- **Per-story issue type** = engineer override if set, else recommendation — **do not** force `analysis.follow_up_stories.issue_type`

Parent merges drafts into Gate 2 presentation. Story-writer remains read-only (no Jira writes).

## Step 7 — GATE 2 (mandatory)

Reuse the approval pattern from `{factory_root}/.cursor/foundry/templates/create-jira-stories-step.md`:

For each draft:

- **Create as-is**
- **Edit title**
- **Edit description**
- **Change issue type**
- **Skip**
- **Cancel all**

**WAIT** for engineer input before any `createJiraIssue`.

## Step 8 — Create receipts

Only for Gate 2–approved drafts:

1. Resolve Atlassian per `atlassian-integration.md` (plugin → legacy → manual).
2. `createJiraIssue` with approved summary, description (markdown), and **approved issue type**.
3. Apply `bug_squash.jira_labels` when configured.
4. Do **not** assign a sprint (backlog only) unless the engineer asks.
5. Optional: link related issues if engineer provides a parent/epic key.

If Atlassian is `manual`, present final markdown for the engineer to paste into Jira.

## Step 9 — Done

Present:

| Key | Type | Summary | Link |
|-----|------|---------|------|

Remind: this skill **stops at receipts**. Implementation is a separate Foundry (or manual) run on the created keys.

**Never** auto-commit, open a PR, or transition board columns unless the engineer explicitly asks in the same session.

---

## Orchestration rules

- Each subagent gets **only** the inputs it needs.
- If a subagent cannot complete its task, stop and report agent name + reason.
- Parent owns Azure Monitor queries — do not delegate log pulls to subagents.
- Parent does not invent the final fix when researcher + builder ran.
- Read-only / propose-only agents may run in parallel when findings are independent; **story-writer stays sequential** after Gate 1.
- Cap parallel researchers at `max_parallel_researchers`.
- Prefer existing resiliency / pooling / batch patterns over “open more connections/resources” — builders must enforce this in `propose_fix`.

## Hard rules

1. **No silent Jira creates** — Gates 0, 1, and 2 are blocking (Gate 0 selects investigation set).
2. **No auto-implement** — propose only; code changes need a separate explicit request.
3. **No builder file edits** in this skill — `propose_fix` only.
4. **Prefer Monitor MCP** over inventing CLI one-liners when MCP works.
5. **Redact secrets** — never paste connection strings, keys, or PII from traces into Jira.
6. **Lookback is explicit** — always echo `{lookback_hours}` before querying.
7. **Auto Azure login** — on unauthorized/expired token, run device-code `az login` yourself; do not tell the engineer to run it manually unless auto-login fails.
8. **App-agnostic** — never hardcode a product, workspace, or role into queries; resolve from prompt / `bug_squash.targets` / discovery + human confirm. Shared workspaces must be scoped to the chosen app.

## Kickoff examples

Plugin `/bug-squash` (or “use bug-squash”). Cloning `.github-private` is not required.

```text
Use bug-squash on Example.Api.
```

```text
Use bug-squash on Example.Api qa, lookback 24h, top 5.
```

```text
Use bug-squash on App.Sonorus prod, last 3 days.
```

```text
Bug-squash — app TobaccoAlcoholChecks.Functions, workspace my-la-workspace, role_filters: ["TobaccoAlcoholChecks"].
```

Any app with Azure Monitor logs works: name the app (or folder), env, and optionally workspace / App Insights / role filters. Missing targets are discovered and confirmed once, then stored under `bug_squash.targets`.

## Additional resources

- KQL templates: [kql-queries.md](kql-queries.md)
- Jira create gate template: `../../factory/templates/create-jira-stories-step.md`
- Atlassian resolution: `../../factory/atlassian-integration.md`
- Subagents: `../../agents/codebase-researcher.md`, `../../agents/backend-builder.md`, `../../agents/client-builder.md`, `../../agents/story-writer.md`
- Quality bar example (refined fix, not connection-per-message): [drafts/2026-07-09-fields-to-sql-closed-connection.md](drafts/2026-07-09-fields-to-sql-closed-connection.md)
