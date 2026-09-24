# Factory delivery steps

Used in **implement.code_review** (code review) and **Step 8** (commit, PR, Jira) after **Step 7 documentation workflow** completes. Work only in **`{app_folder}`**.

Use **FactoryConfig** and **FactoryRunState** from the parent. Do not read `team-variables.md`.

---

## Variables

- `{app_folder}` — app workspace root
- `{issue_key}`, `{developer_first_name}`, `{site_url}` — from ticket packet / FactoryConfig
- `{default_branch}` — from `git default-branch --repo "{app_folder}"` (foundry-invoke)

---

## Step 1 — Code review (implement.code_review)

**If** `templates.code_review` exists in team-variables (paths relative to `{app_folder}` when not using `resolve_templates_from_org`):

Read and follow `@.cursor/commands/templates/code-review-step.md` (or path from variables).

**Else** (generic):

- `git diff --stat` and `git diff` (implementation files only if docs not yet written)
- Acceptance criteria status vs ticket packet
- Test results from factory run
- Validator findings (critical / important / minor)

**ASK HUMAN:** Approve implementation for DevOps/review + later docs + ship, request code changes, or show a specific file.

**Do not commit until Step 7 documentation workflow completes and human approves.** That is **after** Step 6 and after gated Step 7b / Step 7c. When the Step 7b gate is true (`devops.enabled` and `devops.run_before_pr`), wait for Step 7b before Step 7c and docs. When the Step 7c gate is true (`review.enabled` and `review.run_before_pr`), wait for Step 7c before Step 7 docs.

---

## Step 2 — PR extras Jira comment (deliver.scope_comment)

**This is the only factory `addCommentToJiraIssue`.** It runs after the Pre-Step-8 gate checklist and **before** commit/PR. Do not comment earlier in the run or after the PR exists.

When **`jira.enabled`**, **`jira.scope_comments.enabled`**, and **`PrExtrasRegister`** is **non-empty**:

Follow **`{factory_root}/.cursor/foundry/templates/out-of-scope-jira-comment-step.md`** only. That template builds the register, runs **`jira-comment-gate.md`** end to end (single present → **Post** / **Edit** / **Skip** → at most one post), and reports outcomes. Do **not** run the gate a second time or call `addCommentToJiraIssue` outside the gate.

Documents PR files/changes **not called out in the ticket** (e.g. `.github/workflows/sync-prd.yml`, `AGENTS.md`, PRD from factory Step 7).

When register is **empty**, or **`jira.scope_comments.enabled`** is **false**, or **`jira.enabled`** is **false** → **skip Step 8a** automatically. When skipped with a non-empty register, still add the extras table to the PR body when `jira.scope_comments.include_in_pr_body` is true.

**Do not** commit or open a PR until Step 8a completes, human explicitly skips (when Step 8a ran), or Step 8a was **auto-skipped** per the conditions above.

---

## Step 3 — Commit and push (deliver.ship)

**Prerequisite:** Pre-Step-8 `delivery-check` exited 0 **and** Step 8a completed or skipped (when applicable).

### Pre-commit gate (hard stop)

Re-run if FactoryRunState changed:

```foundry-invoke
delivery-check --state "{path-to-run-state.json}"
```

Policy (same rows the CLI checks, plus Step 8a and PR body honesty):

| Check | Pass criteria |
|-------|----------------|
| delivery-check | CLI exit 0 |
| Staged secrets | `git staged-secrets-check` exit 0 **after** `git add`, **before** `git commit` (required — no session hook) |
| Step 8a (when register non-empty + scope comments enabled) | Posted or human skipped |
| PR body honesty | No false "Documentation: N/A" unless factory explicitly stopped |

**If** `templates.commit_push` exists:

Read and follow that template. Use `{issue_key}` as `{JiraTicketNumber}`.

**Else:**

- Stage feature-related files, documentation from Step 7, and workflow changes from Step 7b when applicable
- Run `git staged-secrets-check` (see `commit-push-step.md`) — **required before commit**
- Conventional commit referencing `{issue_key}`
- `git push -u origin HEAD`

---

## Step 4 — Create pull request (deliver.ship)

Follow **`{factory_root}/.cursor/foundry/templates/create-pr-step.md`**.

**PR title:** run `pr-title` per [create-pr-step.md](./create-pr-step.md). Do not copy the commit subject.

Include in PR body:

- Jira link: `{site_url}/browse/{issue_key}`
- Tests added/updated
- AGENTS.md updated (files from Step 7)
- PRD regenerated (path from Step 7)
- `sync-prd.yml` present or created (Step 7d)
- Documentation workflow completed
- **PR work not in ticket:** table from **`PrExtrasRegister`** (same content posted to Jira in Step 8a — e.g. sync-prd, AGENTS.md)
- **GitHub Actions:** when Step 7b ran — devops-builder summary
- **Pre-PR review:** when Step 7c ran — Bugbot and Security summary

**ASK HUMAN:** Confirm PR URL and PR title per **`create-pr-step.md`**.

---

## Step 5 — Jira transition (when enabled)

If `jira.enabled` and `jira_transitions.on_pr_ready` is set and `{atlassian_source}` is not `manual`:

1. `getTransitionsForJiraIssue` for `{issue_key}`
2. `transitionJiraIssue` to configured status (e.g. Ready for Peer Review)
3. Confirm with human

If `{atlassian_source}` is `manual`, ask human to transition the ticket in Jira UI.

---

## Order summary (implementation path)

| Order | Factory step | Activity |
|-------|--------------|----------|
| Earlier | 4–5 | Build + validate |
| **6** | Code review | Human approves implementation |
| **7** | Documentation | `docs pipeline` + selected model (`iot-agents-prd` or `feature-records`) → human approves |
| **7b** | DevOps | devops-builder `pre_pr_review` → human approves |
| **7c** | Pre-PR review | Bugbot + Security → human approves |
| — | Pre-Step-8 checklist | Rows 1–5 (+ 2b when PRD); **excludes** Step 8a |
| **8** | Delivery | **8a** gated PR extras Jira comment (only factory comment; before commit/PR) → `git add` → **`git staged-secrets-check`** → commit → push → PR → Jira transition |
