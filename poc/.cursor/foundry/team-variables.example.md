# Team variables (example)

**Central config:** `team-variables.md` lives in this repo and ships with the **Foundry** plugin. App repos use it via the plugin (run) or a **multi-root Cursor workspace** (contribute). Do not copy variables into app repos.

For a new org fork: copy this file to `team-variables.md` in the same folder and customize.

```bash
# Run once in .github-private only:
cp .cursor/foundry/team-variables.example.md .cursor/foundry/team-variables.md
```

See [WORKSPACE.md](./WORKSPACE.md) for workspace layout and kickoff prompts.

Do **not** put API tokens or passwords here.

---

## Quick start

1. **Run:** enable **Foundry**, open the app repo. Clone this repo only to **edit** factory config.
2. Edit **`team-variables.md`** in this repo when contributing (or copy from this example once).
3. Kick off — board pick shows the **ticket list first**; app is resolved after you pick (ticket hints from the issue first, then `default_app_folder` as fallback). Plugin users do not need `@github-private/...` paths:

```text
Use foundry. Pick from the Jira board.
```

Direct key with explicit app:

```text
Use foundry for YOUR_PROJECT_KEY-123 on your-app.
Follow @your-app/AGENTS.md.
```

---

## Placeholder glossary

| Placeholder | Set in YAML | Resolved at runtime from |
|-------------|-------------|---------------------------|
| `{{project_key}}` | `jira.project_key` | Static in `team-variables.md` |
| `{{site_url}}` | `jira.site_url` | Static |
| `{issue_key}` | — | User input, Jira URL, or `getJiraIssue` |
| `{developer_first_name}` | — | **`atlassianUserInfo`** via plugin or legacy MCP; prompt user if all sources fail |

`{developer_first_name}` is **not** stored in this file—it is fetched each session when `jira.enabled` is true (or when MCP is available).

---

## Field reference

| Key | Required | Used by |
|-----|----------|---------|
| `atlassian.plugin_mcp_server` | No | Atlassian Cursor plugin MCP id (default `plugin-atlassian-atlassian`) |
| `atlassian.plugin_mcp_servers` | No | Ordered plugin MCP ids to try when the primary is unavailable |
| `atlassian.legacy_mcp_servers` | No | Fallback runtime MCP ids (e.g. `user-atlassian` from `~/.cursor/mcp.json`) |
| `jira.enabled` | Yes (for Jira mode) | Step 0 — skip Jira when `false` |
| `jira.project_key` | If Jira enabled | JQL substitution, validation |
| `jira.cloud_id` | No | `getJiraIssue`; empty = resolve via `getAccessibleAtlassianResources` |
| `jira.site_url` | No | Links in ticket packet |
| `jira.issue_key_pattern` | No | Validate user-supplied keys |
| `jira.board_pick_default` | No | Start without a key → board pick flow |
| `jira.pick_list_jql` | For board pick | Sprint/board JQL; must include `{{project_key}}` |
| `jira.pick_list_max_results` | No | Default 50 |
| `jira.claim_on_pick` | No | Assign + transition when picking To Do |
| `git.feature_branch_pattern` | No | Branch preview in packet; delivery |
| `git.pr_title_pattern` | No | Step 8 PR title; default `{issue_key} - {brief_description}` |
| `git.staged_secrets_check.enabled` | No | Default `true` — run `git staged-secrets-check` after `git add` before commit |
| `git.staged_secrets_check.pattern` | No | Full regex replace for staged path blocking (advanced) |
| `git.staged_secrets_check.extra_patterns` | No | List of regexes OR'd onto built-in default (e.g. `local\.settings\.json`) |
| `git.developer_first_name_source` | No | `atlassian` (default), `atlassian_mcp` (alias), or `prompt_user` |
| `git.default_branch` | No | Empty = detect `main` / `master` |
| `jira_transitions.on_start` | No | Optional transition when work starts |
| `jira_transitions.on_pr_ready` | No | Optional transition after PR ready |
| `jira_transitions.on_analysis_complete` | No | Alias for analysis path completion transition |
| `analysis.enabled` | No | `true` enables issue-type pivot for Analysis tickets |
| `analysis.issue_types` | If analysis enabled | Jira `issuetype.name` values that route to analysis path |
| `jira.comments.require_human_approval` | Yes | Must stay `true` — two-turn Post / Edit / Skip before any ticket comment |
| `jira.comments.allowed_step` | Yes | Must be `8a` — implementation Step 8a only, before commit/PR |
| `analysis.deliverable_sections` | No | Sections in analysis report (Confluence / chat; not posted to Jira) |
| `analysis.jira_transitions.on_complete` | No | Transition after A5a Confluence (e.g. Ready for Peer Review) |
| `analysis.follow_up_stories.*` | No | Draft + create follow-up Jira tasks from findings |
| `analysis.confluence.enabled` | No | When `true`, publish approved analysis to Confluence folder (no Jira comment) |
| `analysis.confluence.parent_folder_url` | When Confluence enabled | Target folder URL for analysis pages |
| `analysis.confluence.space_key` | When Confluence enabled | Confluence space key (e.g. `EXAMPLE`) — display / URL only |
| `analysis.confluence.space_id` | When Confluence enabled | Numeric space ID for `createConfluencePage` MCP (required for plugin publish) |
| `analysis.confluence.parent_folder_id` | When Confluence enabled | Numeric folder id from URL |
| `analysis.confluence.title_pattern` | No | Page + doc title; default `{issue_key} {summary}` (Jira Summary verbatim) |
| `analysis.confluence.require_human_approval` | No | Must be `true` — gate before any Confluence publish |
| `analysis.confluence.save_markdown_to_app_repo` | No | Archive markdown under `{app_folder}` after Confluence approval |
| `analysis.confluence.markdown_path_pattern` | No | Default `Documentation/{resolved_title_filename}.md`; `{resolved_title_filename}` is `{resolved_title}` sanitized for OS |
| `analysis.confluence.link_in_jira_comment` | No | Must be `false` — analysis path does not comment on Jira |
| `templates.analysis_delivery` | No | Analysis path Step A5c — transition + confirm (no Jira comment) |
| `templates.analysis_confluence_delivery` | No | Analysis path Step A5a — gated Confluence publish |
| `templates.analysis_confluence_link_comment` | No | Analysis path A5b — skip file (no Jira comment) |
| `templates.jira_comment_gate` | No | Implementation Step 8a two-turn Post / Edit / Skip before PR |
| `templates.create_jira_stories` | No | Analysis path Step A4 — create follow-up issues |
| `org.display_name` | No | Validator / packet display |
| `org.dev_team` | No | Validator context |
| `org.required_labels` | No | Warn if ticket missing labels |
| `templates.create_branch` | No | Step 3b — before build |
| `templates.update_docs` | No | Step 7 — supplement to documentation-workflow |
| `templates.generate_prd` | No | Step 7 — supplement to documentation-workflow |
| `templates.documentation_workflow` | No | Step 7 — full org command (mandatory) |
| `templates.sync_prd_caller` | No | Step 7d — caller workflow YAML template |
| `templates.sync_prd_step` | No | Step 7d — ensure sync-prd.yml exists |
| `templates.sync_prd_validate_script` | No | Windows — `validate-sync-prd-caller.ps1` |
| `templates.sync_prd_validate_script_posix` | No | macOS/Linux — `validate-sync-prd-caller.sh` |
| `templates.code_review` | No | Step 6 — implementation review before 7b/7c/docs |
| `templates.commit_push` | No | Step 8 — delivery |
| Other `templates.*` | No | implement, add_tests, run_tests in build phase |
| `builders.enabled` | No | `false` → single **feature-builder** for Step 4 |
| `builders.build_order` | No | Default `backend` then `client` when both run |
| `devops.enabled` | No | `false` disables devops-builder in foundry (skips Step 7b; no post-PR investigate unless re-enabled) |
| `devops.run_before_pr` | No | `false` skips Step 7b pre-PR SHA scan while `devops.enabled` remains on for CI-only Step 4 work and `investigate_on_ci_failure` |
| `devops.shared_actions_repo` | No | Prefer reusable workflows from this org repo |
| `devops.auto_refresh_same_tag` | No | Bump pinned SHA when tag moved to new commit |
| `devops.investigate_on_ci_failure` | No | Launch `investigate` mode when PR checks fail |
| `devops.workflow_path_globs` | No | Workflow files scanned by devops-builder |
| `review.enabled` | No | `false` skips Step 7c pre-PR Cursor review |
| `review.run_before_pr` | No | `false` skips Step 7c while `review.enabled` may stay on for manual `/review` |
| `review.mode` | No | `both` (default): Bugbot then Security; or `bugbot`, `security`, `ask` |
| `review.diff` | No | `branch changes` (default) or `uncommitted changes` |
| `templates.pre_pr_review` | No | Step 7c — pre-PR review template |
| `templates.story_refinement_presentation` | No | Step 0a — two-turn AC presentation before approval |
| `story_writer.enabled` | No | `false` skips gap analysis on thin Jira tickets |
| `story_writer.run_on_jira` | No | After `getJiraIssue`, before research |
| `story_writer.run_on_free_text` | No | Step 0b free-text kickoff |
| `story_writer.require_full_ac_presentation` | No | `true` (default): full suggested AC in chat, STOP, then approval on next turn |
| `bug_squash.enabled` | No | Enables bug-squash skill defaults |
| `bug_squash.default_lookback_hours` | No | Default **168** (7 days); override in prompt per run |
| `bug_squash.default_environment` | No | Default **prod**; override in prompt (`dev` / `qa` / `prod`) |
| `bug_squash.top_n` | No | Max error groups to list (default 10) |
| `bug_squash.max_parallel_researchers` | No | Cap parallel `bug_triage` Task launches (default 3) |
| `bug_squash.require_builder_critique` | No | `true` → backend/client `propose_fix` before Gate 1 |
| `bug_squash.create_jira_receipts` | No | After engineer gates, draft/create Jira receipts |
| `bug_squash.jira_labels` | No | Labels applied to triage-created issues |
| `bug_squash.azure_tenant` | No | Entra tenant for auto `az login` when unauthorized |
| `bug_squash.azure_login_scope` | No | Scope for device-code login (default management ARM) |
| `bug_squash.azure_subscriptions` | No | Map `dev`/`qa`/`prod` → subscription name or GUID |
| `bug_squash.targets` | No | Per-app/env map: workspace, App Insights, `role_filters` for shared LAW |
| `bug_squash.targets.*.role_filters` | No | `AppRoleName` substrings — required when telemetry is shared across apps |
| `bug_squash.targets.*.resource_id_filters` | No | Optional `_ResourceId` substrings when role alone is ambiguous |
| `workspace.resolve_templates_from_org` | No | `true` when app repo has no `.cursor/commands` (templates in org repo) |

---

## Scenario E — Thin Jira tickets (story-writer)

**Use when:** Tickets often lack AC or clear scope; factory should propose gaps before research.

```yaml
# story_writer:
#   enabled: true
#   run_on_jira: true
#   run_on_free_text: true
#   require_full_ac_presentation: true  # two-turn Step 0a gate (see story-refinement-presentation-step.md)
```

After board pick or direct key, **story-writer** runs (read-only), parent presents **full suggested AC** and **STOP**s, then human approves on the next turn before **codebase-researcher**.

---

## Scenario H — Bug squash

**Use when:** Engineers want top production/QA errors from Azure Monitor MCP, pressure-tested fix proposals, and gated Jira receipts.

```yaml
# bug_squash:
#   enabled: true
#   default_lookback_hours: 168   # 7 days; override in prompt (e.g. lookback 24h)
#   default_environment: prod     # override in prompt with dev / qa / prod
#   top_n: 10
#   max_parallel_researchers: 3
#   require_builder_critique: true  # backend/client propose_fix before Gate 1
#   create_jira_receipts: true
#   azure_tenant: "your-entra-tenant-guid"
#   azure_login_scope: "https://management.azure.com//.default"
#   azure_subscriptions:
#     prod: "Production"
#     qa: ""
#     dev: ""
#   jira_labels:
#     - bug-squash
#   # One entry per app — skill is reusable; fill as you confirm telemetry
#   targets:
#     Your.App.Folder:
#       prod:
#         workspace: "your-law-name-or-id"
#         resource_group: "your-rg"
#         app_insights: "your-ai-component"   # optional if workspace-only
#         role_filters: ["YourRoleName"]      # required on shared workspaces
#         resource_id_filters: ["YourFuncApp"]
```

Kickoff:

```text
Use bug-squash on <any-app-folder>.
```

Works for **any** solution with Azure Monitor logs. Name the app (or folder), env, and optionally workspace / App Insights / role filters. Defaults to **prod** and **7d** lookback. On unauthorized/expired Azure tokens, the skill **auto-runs device-code `az login`** then sets the env subscription. Shared workspaces are scoped via `role_filters`. Flow: Monitor → Gate 0 → researcher → builder `propose_fix` → Gate 1 → story-writer → Gate 2 → create. Issue type is chosen **per finding**. Builders do **not** edit code in this skill.

---

## Scenario G — Analysis tickets (pivot path)

**Use when:** Sprint boards include **Analysis** investigation tickets that deliver findings via Confluence + Jira, not code PRs.

```yaml
# analysis:
#   enabled: true
#   issue_types:
#     - Analysis
#   deliverable_sections:
#     - findings
#     - kql_queries
#     - qa_repro_steps
#     - recommendations
#   jira_transitions:
#     on_complete: "Ready for Peer Review"
#   follow_up_stories:
#     enabled: true
#     issue_type: Task
#     labels: []
#     link_to_parent: true
#   confluence:
#     enabled: true
#     parent_folder_url: "https://your-org.atlassian.net/wiki/spaces/YOURSPACE/folder/123456789/Jira+Analysis+Tickets"
#     space_key: YOURSPACE
#     space_id: "123456789"
#     parent_folder_id: "123456789"
#     title_pattern: "{issue_key} {summary}"
#     require_human_approval: true
#     save_markdown_to_app_repo: true
#     markdown_path_pattern: "Documentation/{resolved_title_filename}.md"
#     link_in_jira_comment: false  # analysis must not comment; Step 8a before PR only
# jira_transitions:
#   on_analysis_complete: "Ready for Peer Review"
# templates:
#   analysis_delivery: ".cursor/foundry/templates/analysis-delivery-steps.md"
#   analysis_confluence_delivery: ".cursor/foundry/templates/analysis-confluence-delivery-step.md"
#   analysis_confluence_link_comment: ".cursor/foundry/templates/analysis-confluence-link-comment-step.md"
#   create_jira_stories: ".cursor/foundry/templates/create-jira-stories-step.md"
```

When `issuetype.name` matches `analysis.issue_types`, factory skips branch/build/PR and runs: story-writer (deliverables) → codebase-researcher (deep dive) → documentation-writer (report draft) → optional follow-up stories → **A5a gated Confluence publish** → **A5c transition to Ready for Peer Review**. Analysis does **not** comment on Jira. Factory ticket comments run only at **implementation Step 8a before the PR**.

---

## Scenario D — Split backend + client builders

**Use when:** App has distinct server and UI layers (API + SPA, .NET + React, etc.).

```yaml
# builders:
#   enabled: true
#   build_order:
#     - backend
#     - client
```

Application path routing is declared in `{app_folder}/.foundry/app.yaml` (`builders.default_owner` and `builders.routes`). Do not put app path globs in the team profile.

Step 4 runs **backend-builder** then **client-builder** when the brief needs both; **devops-builder** runs in **Step 7b** after Step 6 when `devops.enabled` and `devops.run_before_pr` are both true (SHA pin/refresh scan); **Step 7c** runs Bugbot + Security on the implementation diff when `review.enabled` and `review.run_before_pr` are both true (default `review.mode: both`); **documentation-writer** runs in **Step 7** after that critic cycle; factory Step 8 commits code + docs + workflow changes together.

---

## Scenario I — DevOps / GitHub Actions (Step 7b)

**Use when:** Every foundry PR should keep third-party actions SHA-pinned; optionally auto-refresh stale pins on the same tag via `auto_refresh_same_tag`.

```yaml
# devops:
#   enabled: true
#   run_before_pr: true
#   third_party_owners_exclude:
#     - actions
#     - github
#   pin_comment_format: "# {owner}/{repo}@{tag}"
#   auto_refresh_same_tag: true
#   workflow_path_globs:
#     - ".github/workflows/**/*.yml"
#     - ".github/workflows/**/*.yaml"
```

After Step 6 approval, **devops-builder** runs `pre_pr_review`: pin unpinned third-party actions; refresh SHAs when tags moved **when `devops.auto_refresh_same_tag` is true** (when false, report drift in `SameTagDrift` without editing); report major-version bump candidates. Human approves before Step 7c and Step 7 docs.

**CI broke?** Launch **devops-builder** with `mode: investigate` — uses `gh run list`, `gh run view --log-failed`, and job API to root-cause failures (pinning, permissions, secrets, reusable workflow inputs). Read-only until human approves a fix.

For **CI-only tickets**, launch **devops-builder** in `implement` mode at Step 4 instead of backend/client builders.

---

## Scenario J — Pre-PR Cursor review (Step 7c)

**Use when:** Every foundry run should run local Bugbot + Security review on the implementation branch diff before documentation and commit/PR.

```yaml
# review:
#   enabled: true
#   run_before_pr: true
#   mode: both           # bugbot | security | both | ask
#   diff: branch changes # branch changes | uncommitted changes
```

After Step 6 (and Step 7b when gated), the parent agent follows **`pre-pr-review-step.md`**: launches **`bugbot`** then **`security-review`** subagents (when `mode: both`), presents findings, human approves before **Step 7 documentation**.

This is the **local** `/review` behavior — not the GitHub **Cursor Bugbot** PR check (that runs after the PR is created if enabled).

---

## Scenario A — Jira + sprint pick list

**Use when:** Team uses Jira sprints; developer may pick a ticket from a list.

```yaml
# jira:
#   enabled: true
#   cloud_id: ""
#   project_key: ENG
#   issue_key_pattern: "^[A-Z]+-\\d+$"
#   pick_list_jql: |
#     project = {{project_key}} AND sprint in openSprints() AND (
#       status = "To Do" OR
#       (status = "In Progress" AND assignee = currentUser())
#     )
#   site_url: "https://your-org.atlassian.net"
# git:
#   developer_first_name_source: atlassian_mcp
#   feature_branch_pattern: "{developer_first_name}/{issue_key}"
# jira_transitions:
#   on_start: "In Progress"
#   on_pr_ready: "Ready for Peer Review"
```

---

## Scenario B — Jira, single ticket only

**Use when:** Developer always passes `PROJ-123` or a browse URL; no pick list.

```yaml
# jira:
#   enabled: true
#   project_key: ENG
#   site_url: "https://your-org.atlassian.net"
# git:
#   developer_first_name_source: atlassian_mcp
#   feature_branch_pattern: "{developer_first_name}/{issue_key}"
```

---

## Scenario C — Jira disabled (free-text factory)

**Use when:** No issue tracker MCP; feature ideas come from chat only.

```yaml
# jira:
#   enabled: false
# git:
#   developer_first_name_source: atlassian_mcp
#   feature_branch_pattern: "feature/{issue_key}"
```

If MCP is still configured, `atlassianUserInfo` can still supply `{developer_first_name}` for branches when you adopt Jira later.

---

## Scenario D — With legacy step templates

**Use when:** Repo also copies `.cursor/commands/templates/` from an org command pack.

```yaml
# jira:
#   enabled: true
#   project_key: ENG
#   site_url: "https://your-org.atlassian.net"
# git:
#   developer_first_name_source: atlassian_mcp
#   feature_branch_pattern: "{developer_first_name}/{issue_key}"
# templates:
#   create_branch: ".cursor/commands/templates/create-branch-step.md"
#   implement: ".cursor/commands/templates/implement-changes-step.md"
#   add_tests: ".cursor/commands/templates/add-tests-step.md"
#   run_tests: ".cursor/commands/templates/run-tests-step.md"
#   update_docs: ".cursor/commands/templates/update-docs-step.md"
#   generate_prd: ".cursor/commands/templates/generate-prd-step.md"
#   code_review: ".cursor/commands/templates/code-review-step.md"
#   commit_push: ".cursor/commands/templates/commit-push-step.md"
```

Factory skills `@`-reference these paths; templates are **not** copied or modified.

---

## Scenario F — Multiple app repos in one workspace

**Use when:** `github-private` + several services in the same workspace; you name the target per run.

```yaml
# workspace:
#   org_folder: github-private
#   default_app_folder: Example.Api
#   app_folders:
#     - Example.Api
#     - Example.Api
```

Kickoff: `Use foundry. Pick from the Jira board.` — ticket list first; app resolved after pick. Or `Use foundry for ENG-123 on Example.Api` for a direct key with explicit app.

---

## Scenario E — Org metadata + required labels

**Use when:** Validator should warn if Jira tickets lack team labels.

```yaml
# jira:
#   enabled: true
#   project_key: ENG
# org:
#   display_name: Platform Engineering
#   dev_team: Backend
#   required_labels:
#     - TechCertified
# git:
#   developer_first_name_source: atlassian_mcp
#   feature_branch_pattern: "{developer_first_name}/{issue_key}"
```

---

## Anti-patterns

- Do not commit secrets (API keys, PATs, `.env` values).
- Do not copy `team-variables.md` into application repos.
- Do not hardcode project keys in factory skills/agents—only in `team-variables.md` here.

---

## Active configuration (edit after copy to team-variables.md)

Uncomment and customize Scenario A–E above, **or** use this minimal starter:

```yaml
workspace:
  org_folder: github-private
  org_repo_path_env: GITHUB_PRIVATE   # absolute org repo path for shell scripts (see WORKSPACE.md)
  default_app_folder: ""          # e.g. Example.Api — fallback after ticket hints / single-app workspace
  app_folders: []                 # optional: [Example.Api, Example.Api]

atlassian:
  plugin_mcp_server: plugin-atlassian-atlassian
  plugin_mcp_servers:
    - plugin-atlassian-atlassian
  legacy_mcp_servers:
    - user-atlassian

jira:
  enabled: false
  project_key: ""
  cloud_id: ""
  site_url: ""
  issue_key_pattern: "^[A-Z]+-\\d+$"
  board_pick_default: true
  pick_list_max_results: 50
  claim_on_pick: true
  pick_list_jql: ""
  comments:
    require_human_approval: true
    allowed_step: "8a"
  # Step 8a: Jira comment for PR files/changes NOT in the ticket (e.g. sync-prd.yml, AGENTS.md) — before commit/PR.
  scope_comments:
    enabled: true
    require_human_approval: true
    include_in_pr_body: true
    document_deferred: false

git:
  developer_first_name_source: atlassian
  default_branch: ""
  feature_branch_pattern: "feature/{issue_key}"
  pr_title_pattern: "{issue_key} - {brief_description}"
  staged_secrets_check:
    enabled: true
    extra_patterns: []

jira_transitions:
  on_start: ""
  on_pr_ready: ""
  on_analysis_complete: "Ready for Peer Review"

analysis:
  enabled: false
  issue_types: []
  deliverable_sections: []
  jira_transitions:
    on_complete: "Ready for Peer Review"
  follow_up_stories:
    enabled: false
    issue_type: Task
    labels: []
    link_to_parent: true
  confluence:
    enabled: false
    parent_folder_url: ""
    space_key: ""
    space_id: ""
    parent_folder_id: ""
    title_pattern: "{issue_key} {summary}"
    require_human_approval: true
    save_markdown_to_app_repo: true
    markdown_path_pattern: "Documentation/{resolved_title_filename}.md"
    link_in_jira_comment: false

bug_squash:
  enabled: true
  default_lookback_hours: 168
  default_environment: prod
  top_n: 10
  create_jira_receipts: true
  azure_tenant: ""
  azure_login_scope: "https://management.azure.com//.default"
  azure_subscriptions:
    prod: ""
    qa: ""
    dev: ""
  jira_labels:
    - bug-squash
  targets: {}

org:
  display_name: ""
  dev_team: ""
  required_labels: []

templates:
  create_branch: ""
  implement: ""
  add_tests: ""
  run_tests: ""
  update_docs: ""
  generate_prd: ""
  documentation_workflow: ""
  sync_prd_caller: ""
  sync_prd_step: ""
  sync_prd_validate_script: ".cursor/foundry/scripts/validate-sync-prd-caller.ps1"
  sync_prd_validate_script_posix: ".cursor/foundry/scripts/validate-sync-prd-caller.sh"
  code_review: ""
  commit_push: ""
  analysis_delivery: ""
  analysis_confluence_delivery: ""
  analysis_confluence_link_comment: ""
  create_jira_stories: ""
```
