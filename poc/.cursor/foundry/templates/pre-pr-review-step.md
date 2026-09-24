# Pre-PR Cursor review (implement.pre_pr_review)

Run in **`{app_folder}`** after **Step 6 code review approval** and **Step 7b DevOps approval** (when Step 7b ran). **Before Step 7 documentation.**

Uses Cursor **local** review subagents (same behavior as the `/review` command). This is **not** the GitHub **Cursor Bugbot** PR check — that still runs on the PR after push if enabled for the repo.

---

## Gate

Run this step only when **`review.enabled` is true (default)** and **`review.run_before_pr` is true (default)**.

Skip when either is false — proceed to **Step 7 documentation**.

---

## Variables (from team-variables)

| Key | Default | Purpose |
|-----|---------|---------|
| `review.enabled` | `true` | Master switch for Step 7c |
| `review.run_before_pr` | `true` | Run before commit/PR |
| `review.mode` | `both` | `bugbot` \| `security` \| `both` \| `ask` |
| `review.diff` | `branch changes` | `branch changes` \| `uncommitted changes` |
| `templates.pre_pr_review` | this file | Override path when set |

When `review.mode` is `ask`, use **AskQuestion** with options **Bugbot** and **Security Review** (same as `/review`). When `both`, run **Bugbot** then **Security Review** sequentially on the same diff.

---

## Procedure (parent agent)

Work on the feature branch in `{app_folder}`. Default diff scope: **`branch changes`** (merge-base with default branch, including committed, staged, and unstaged changes).

Resolve critics, then launch each through Foundry so receipts bind to this run:

```foundry-invoke
review critics --mode {mode}
```

For each critic (`bugbot` and/or `security-review`):

```foundry-invoke
worker launch-packet --state "{state_path}" --agent {critic} --mode review
```

Launch exactly one Task per critic with the packet prompt (`run_in_background: false`). When mode is `both`, run Bugbot then Security Review sequentially. Complete each from `craft_staging_path` / `launch_id`. After both critics:

```foundry-invoke
review validate-receipts --state "{state_path}"
```

If the subagent cannot compute the diff, retry once with `Diff: natural language` and a **Change Description** per file (see `review-bugbot` skill).

Summarize findings in a table: **Severity | Location (file:line) | Finding**. If no issues: note "Bugbot found no bugs." / "Security review found no issues."

---

## ReviewChangeReport (return to parent)

```markdown
## Pre-PR review (Step 7c)
- Mode: {bugbot | security | both}
- Diff: {branch changes | uncommitted changes}
- Bugbot: {N findings | skipped | no bugs}
- Security: {N findings | skipped | no issues}
- Critical/high findings: {count or none}
```

Include merged finding tables when any issues were reported.

---

## Human gate

**ASK HUMAN:** Approve for ship, request fixes (route to Step 4 builders only — not documentation-writer), or accept documented risk.

- **Request fixes:** apply implementation changes, re-run Step 7c (or only the review type that flagged issues when mode is `both`). Doc-only notes wait for Step 7.
- **Approved / accept risk:** proceed to **Step 7 documentation**. **Do not commit or open a PR yet.**

**Never** commit or open a PR until Step 7c completes and human approves when the Step 7c gate is true.

---

## Optional PR body note (Step 8)

When Step 7c ran, include in the PR body under **Checklist** or **Pre-PR review**:

- Pre-PR Cursor review ({mode}): Bugbot — {summary}; Security — {summary}
