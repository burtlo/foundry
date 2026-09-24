# FactoryRunState

Parent-owned. Initialize after the ticket packet (Step 0 / 0p). Update after every gated step. This object is the **evidence** for Pre-Step-8; the checklist in the skill remains visible policy.

**Wave 1:** write this JSON to a temp file and run:

```foundry-invoke
delivery-check --state "{path-to-run-state.json}"
```

Exit 0 only when every required row passes. Do not `git commit`, `git push`, or `gh pr create` when the check fails.

Human STOP gates still apply. This file must not be treated as approval.

---

## Keys

Start empty / null after the ticket packet. Fill as the run proceeds.

| Key | Type | When set |
|------|------|----------|
| `run_mode` | `analysis` \| `implementation` | Step 0p |
| `issue_key` | string or null | Ticket packet / `issue-key parse` |
| `app_folder` | string | After implementation target resolve |
| `factory_root` | string | Variables contract |
| `developer_first_name` | string or null | `atlassianUserInfo` |
| `atlassian_source` | `plugin` \| `legacy_mcp` \| `manual` | Atlassian integration |
| `default_branch` | string | `git default-branch` (short name, never `origin/main`) |
| `resolved_pr_title` | string or null | `pr-title` before `gh pr create` |
| `step6_approved` | boolean | Human approved implementation for DevOps/review + later docs + ship |
| `step7_doc_change_report` | `received` \| `missing` | documentation-writer returned DocChangeReport |
| `step7_human_approved` | boolean | Human approved documentation-workflow Step 8 |
| `prd_created_or_updated` | boolean | Step 7 created or updated a PRD |
| `sync_prd_ok` | boolean | `prd-sync validate` exit 0 (required when `prd_created_or_updated`) |
| `devops_enabled` | boolean | From FactoryConfig |
| `devops_run_before_pr` | boolean | From FactoryConfig |
| `step7b_report` | `received` \| `missing` \| `skipped` | devops-builder `pre_pr_review` |
| `step7b_approved` | boolean | Human approved DevOps (empty diff OK) |
| `review_enabled` | boolean | From FactoryConfig |
| `review_run_before_pr` | boolean | From FactoryConfig |
| `step7c_report` | `received` \| `missing` \| `skipped` | ReviewChangeReport |
| `step7c_approved` | boolean | Human approved pre-PR review |
| `feature_branch_ok` | boolean | Feature branch checked out; not default branch unless factory stopped |
| `pr_extras_register` | array | Diff + IncludedInPrOutsideTicket; empty OK when PR matches ticket |
| `step8a_status` | `posted` \| `skipped` \| `auto_skipped` \| `pending` | Not a Pre-Step-8 row; required before commit when Step 8a runs |

---

## Example (implementation, gates on, ready for delivery-check)

```json
{
  "run_mode": "implementation",
  "issue_key": "TICKET-2327",
  "app_folder": "Example.Api",
  "factory_root": "C:/repos/ORG/factory",
  "developer_first_name": "Alex",
  "atlassian_source": "plugin",
  "default_branch": "main",
  "resolved_pr_title": null,
  "step6_approved": true,
  "step7_doc_change_report": "received",
  "step7_human_approved": true,
  "prd_created_or_updated": true,
  "sync_prd_ok": true,
  "devops_enabled": true,
  "devops_run_before_pr": true,
  "step7b_report": "received",
  "step7b_approved": true,
  "review_enabled": true,
  "review_run_before_pr": true,
  "step7c_report": "received",
  "step7c_approved": true,
  "feature_branch_ok": true,
  "pr_extras_register": [],
  "step8a_status": "auto_skipped"
}
```

---

## Pre-Step-8 mapping

| # | Gate | Pass when |
|---|------|-----------|
| 1 | Step 6 | `step6_approved` is true |
| 2 | Step 7 | `step7_doc_change_report` is `received` and `step7_human_approved` is true |
| 2b | sync-prd | `prd_created_or_updated` is false, **or** `sync_prd_ok` is true |
| 3 | Step 7b | `devops_enabled` and `devops_run_before_pr` are both true → `step7b_report` is `received` and `step7b_approved` is true; otherwise skipped |
| 4 | Step 7c | `review_enabled` and `review_run_before_pr` are both true → `step7c_report` is `received` and `step7c_approved` is true; otherwise skipped |
| 5 | Feature branch | `feature_branch_ok` is true |
| 5b | PrExtrasRegister | `pr_extras_register` is an array (empty allowed) |

`delivery-check` does not care about fill order. The parent must still run Step 6 → gated 7b/7c → Step 7 docs, then this check, then Step 8.
