# Team variables (legacy markdown; prefer `.cursor/foundry/profiles/*.yaml`)

Edit this file in the **factory clone** only when a skill still reads markdown team-variables. Runtime Foundry uses YAML profiles. App repos do not have a copy.

See [team-variables.example.md](./team-variables.example.md) for field reference.

Each factory run targets **one** app (prompt → workspace root → `workspace.default_app_folder`).

```yaml
workspace:
  org_folder: github-private
  # Shell scripts: export absolute org repo path (see WORKSPACE.md → {org_repo_path})
  org_repo_path_env: GITHUB_PRIVATE
  # Pilot app fallback when ticket/workspace give no signal (ticket hints win on board pick)
  default_app_folder: Example.Api
  app_folders:
    - Example.Api
  # App repos have no .cursor/commands — use step templates from org repo
  resolve_templates_from_org: true

# Atlassian integration: plugin first, legacy MCP fallback, manual Jira URL last.
# See .cursor/foundry/atlassian-integration.md
atlassian:
  # Cursor plugin MCP id when enabled in Settings → MCP (per workspace)
  plugin_mcp_server: plugin-atlassian-atlassian
  # Try each id in order when plugin_mcp_server is unavailable
  plugin_mcp_servers:
    - plugin-atlassian-atlassian
  # Primary runtime id: ~/.cursor/mcp.json "atlassian" → user-atlassian (call mcp_auth when STATUS requires it)
  legacy_mcp_servers:
    - user-atlassian

jira:
  enabled: true
  # Same project + board JQL as ticket-workflow Step 1
  project_key: TICKET
  issue_key_pattern: "^TICKET-\\d+$"
  board_pick_default: false
  pick_list_max_results: 50
  claim_on_pick: false
  pick_list_jql: |
    project = {{project_key}} AND sprint in openSprints() AND (
      status = "To Do" OR
      (status = "In Progress" AND assignee = currentUser())
    )
  site_url: "https://example.atlassian.net"
  # The only factory addCommentToJiraIssue is Step 8a (before commit/PR). Analysis must not comment.
  comments:
    require_human_approval: true   # two-turn gate — present draft, STOP, post only after engineer replies Post
    allowed_step: "8a"             # implementation Step 8a only; never A2/A5 or after the PR exists
  # Step 8a: Jira comment listing PR changes NOT called out in the ticket (e.g. sync-prd.yml, AGENTS.md from factory Step 7) — before commit/PR.
  scope_comments:
    enabled: false
    require_human_approval: true   # inherited from jira.comments; never post without Post
    include_in_pr_body: true       # same table under ## PR work not in ticket in PR body
    document_deferred: false        # when true, also comment on work deferred (not in PR); default off

git:
  # atlassian = plugin-first then legacy MCP; atlassian_mcp is legacy alias
  developer_first_name_source: atlassian
  default_branch: ""
  feature_branch_pattern: "eval/{codename}/{issue_key}"
  pr_title_pattern: "{issue_key} - {brief_description} [{codename}]"
  staged_secrets_check:
    enabled: true
    # pattern: null                 # set to replace built-in default entirely
    extra_patterns:
      - 'local\.settings\.json'    # Azure Functions local config

jira_transitions:
  on_start: ""
  on_pr_ready: ""
  # Alias for analysis path; falls back to analysis.jira_transitions.on_complete when set
  on_analysis_complete: ""

org:
  display_name: Foundry
  dev_team: Engineering
  required_labels: []

# Analysis pivot (foundry): issue types that skip build/PR and deliver via Confluence (no Jira comment).
analysis:
  enabled: true
  issue_types:
    - Analysis
  deliverable_sections:
    - findings
    - kql_queries
    - qa_repro_steps
    - recommendations
  jira_transitions:
    on_complete: ""
  follow_up_stories:
    enabled: false
    issue_type: Task
    labels: []
    link_to_parent: true
  confluence:
    enabled: false
    # Parent folder for completed analysis write-ups (DOTNET IoT → Jira Analysis Tickets)
    parent_folder_url: "https://example.atlassian.net/wiki/spaces/EXAMPLE/folder/0"
    space_key: EXAMPLE
    # Numeric space ID for createConfluencePage MCP (space_key alone may fail — resolve via getConfluenceSpaces)
    space_id: "94011398"
    parent_folder_id: "396132474"
    title_pattern: "{issue_key} {summary}"
    require_human_approval: true
    save_markdown_to_app_repo: true
    # Filename mirrors Confluence page title ({resolved_title}); sanitize / \ : * ? " < > | for filesystem
    markdown_path_pattern: "Documentation/{resolved_title_filename}.md"
    link_in_jira_comment: false  # never post analysis comments; factory comments are Step 8a (before PR) only

# Story refinement after Jira fetch (intake.refine). Helps thin tickets.
story_writer:
  enabled: true
  run_on_jira: true
  run_on_free_text: true
  # Step 0a two-turn gate: full suggested AC in chat before any approval prompt (see story-refinement-presentation-step.md)
  require_full_ac_presentation: true

# Bug squash skill (Azure Monitor MCP → researcher → builder propose_fix → gated Jira).
# Lookback hours default 168 (7d); override per run in the user prompt.
# Issue type is chosen per finding (Bug/Task/Story/Analysis) — not a fixed default.
# Research runs only on Gate 0–selected findings; builders refine fixes before Gate 1.
bug_squash:
  enabled: true
  default_lookback_hours: 168
  default_environment: prod
  top_n: 10
  create_jira_receipts: false
  max_parallel_researchers: 3
  require_builder_critique: true
  # Auto-login when az/MCP auth fails (device-code flow in agent shell)
  azure_tenant: ""
  azure_login_scope: "https://management.azure.com//.default"
  # Map environment → Azure subscription name or GUID (az account set)
  azure_subscriptions:
    prod: "Production"
    qa: ""   # fill when known
    dev: ""  # fill when known
  jira_labels:
    - bug-squash
  # Per-app telemetry map — reusable for any solution.
  # Key = workspace.app_folders entry (or any app folder name). Nested key = env.
  # On shared LAW/AI, set role_filters so top errors are scoped to that app.
  # After engineer confirms a new target, persist it here for the next run.
  # Schema: workspace, resource_group, app_insights, app_insights_resource_group,
  #         resource_id, table, role_filters[], resource_id_filters[]
  targets:
    Example.Api:
      prod:
        workspace: "prod-la-shared-north"
        resource_group: "prod-rg-shared-north"
        app_insights: "prod-ai-example-north"
        app_insights_resource_group: "prod-rg-example-north"
        role_filters:
          - "ExampleApi"
        resource_id_filters:
          - "ExampleApi"


# Split code writers (foundry Step 4). Application path routing lives in
# `{app_folder}/.foundry/app.yaml` `builders.routes`, not the team profile.
builders:
  enabled: true
  build_order:
    - backend
    - client

# GitHub Actions / CI (implement.devops_review — devops-builder before PR when enabled + run_before_pr).
devops:
  enabled: true
  run_before_pr: false  # false skips Step 7b pre-PR SHA scan; enabled may stay true for CI-only Step 4 / investigate
  # Marketplace/community actions — must be SHA-pinned (exclude GitHub + org owners)
  third_party_owners_exclude:
    - actions
    - github
  pin_comment_format: "# {owner}/{repo}@{tag}"
  auto_refresh_same_tag: false
  workflow_path_globs:
    - ".github/workflows/**/*.yml"
    - ".github/workflows/**/*.yaml"
  # When true, parent may launch devops-builder investigate mode after failed PR checks
  investigate_on_ci_failure: true

# Cursor pre-PR review (implement.pre_pr_review — local Bugbot + Security before commit/PR).
review:
  enabled: true
  run_before_pr: true  # false skips Step 7c; enabled may stay true for manual /review outside factory
  mode: both           # bugbot | security | both | ask (ask = same as /review command picker)
  diff: branch changes # branch changes | uncommitted changes

templates:
  create_branch: ".cursor/commands/templates/create-branch-step.md"
  implement: ".cursor/commands/templates/implement-changes-step.md"
  add_tests: ".cursor/commands/templates/add-tests-step.md"
  run_tests: ".cursor/commands/templates/run-tests-step.md"
  update_docs: ".cursor/commands/templates/update-docs-step.md"
  generate_prd: ".cursor/commands/templates/generate-prd-step.md"
  documentation_workflow: ".cursor/commands/documentation-workflow.md"
  sync_prd_caller: ".cursor/foundry/templates/sync-prd-caller.yml"
  sync_prd_step: ".cursor/foundry/templates/sync-prd-step.md"
  # Windows: .ps1   macOS/Linux: .sh — pick by OS (agent-shell)
  sync_prd_validate_script: ".cursor/foundry/scripts/validate-sync-prd-caller.ps1"
  sync_prd_validate_script_posix: ".cursor/foundry/scripts/validate-sync-prd-caller.sh"
  code_review: ".cursor/commands/templates/code-review-step.md"
  pre_pr_review: ".cursor/foundry/templates/pre-pr-review-step.md"
  commit_push: ".cursor/commands/templates/commit-push-step.md"
  analysis_delivery: ".cursor/foundry/templates/analysis-delivery-steps.md"
  analysis_confluence_delivery: ".cursor/foundry/templates/analysis-confluence-delivery-step.md"
  analysis_confluence_link_comment: ".cursor/foundry/templates/analysis-confluence-link-comment-step.md"
  jira_comment_gate: ".cursor/foundry/templates/jira-comment-gate.md"
  create_jira_stories: ".cursor/foundry/templates/create-jira-stories-step.md"
  story_refinement_presentation: ".cursor/foundry/templates/story-refinement-presentation-step.md"
  out_of_scope_jira_comment: ".cursor/foundry/templates/out-of-scope-jira-comment-step.md"
```

Template paths resolve from the **factory root** (plugin bundle, or `github-private` when cloned) when `resolve_templates_from_org: true`.

**Implementation path:** branch → build/tests → validate → **code review (Step 6)** → **devops / GitHub Actions (Step 7b when `devops.enabled` and `devops.run_before_pr`)** → **Cursor pre-PR review (Step 7c when `review.enabled` and `review.run_before_pr`)** → **documentation-workflow (Step 7)** → commit → PR → Jira (`delivery-steps.md`, `pre-pr-review-step.md`, `post-build-steps.md`).

**Analysis path:** deliverables → deep research → report draft (chat/Confluence only — **no Jira comment**) → optional follow-up stories → **A5a Confluence publish (gated)** → **A5c transition to Ready for Peer Review** (`analysis-confluence-delivery-step.md`, `analysis-delivery-steps.md`, `create-jira-stories-step.md`). Factory Jira comments run only on the **implementation** path at **Step 8a before the PR**.
