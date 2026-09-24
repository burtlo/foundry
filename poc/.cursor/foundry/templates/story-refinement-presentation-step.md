# Story refinement presentation (intake.present_ac)

Run after **`story-writer`** returns and **before** any approval prompt or downstream subagent.

Applies when **`story_writer.require_full_ac_presentation`** is `true` (default in team-variables).

---

## Gate

When `story_writer.enabled` is `true` and `require_full_ac_presentation` is `true` (default):

1. Parent **must read and follow this template** end to end.
2. Step 0a is a **two-turn minimum** — presentation turn, then approval turn.
3. **STOP** at the end of the presentation turn. Do not proceed in the same turn.

Skip this template only when `story_writer.require_full_ac_presentation` is explicitly `false` (legacy: inline presentation in SKILL.md Step 0a still applies).

---

## Variables (from team-variables)

| Key | Default | Purpose |
|-----|---------|---------|
| `story_writer.enabled` | `true` | Master switch for Step 0a |
| `story_writer.require_full_ac_presentation` | `true` | Enforce two-turn AC presentation |
| `templates.story_refinement_presentation` | this file | Override path when set |

---

## Procedure (parent agent)

After `story-writer` completes, send **one user-facing message** with sections **in this order**. Do not reorder or omit sections.

### 1. Header

```markdown
## Feature Factory — {issue_key} (Step 0a — story refinement)
```

Include: run mode, `{app_folder}`, branch preview if known.

### 2. Ticket packet (summary table)

Key, summary, issue type, status, priority, parent epic, labels, implementation target.

### 3. Original Jira acceptance criteria

**Verbatim** numbered list from `getJiraIssue`. If Jira has no AC, state **(none in Jira)** explicitly.

### 4. Story-writer report (scannable)

Include:

- **Readiness**
- **MissingOrWeak** (bullets)
- **SuggestedStory** (if provided)
- **ScopeNotes** (in scope / out of scope)

Do **not** substitute a one-line summary for section **3** (Original Jira AC / Expected Output) or section **5** (Suggested AC / Deliverable checklist for human review).

### 5. Suggested acceptance criteria for human review

Copy **`SuggestedAcceptanceCriteria`** from story-writer **verbatim** — full numbered list, every item marked `(from Jira)` or `(proposed)`.

If story-writer also returned **`AcceptanceCriteriaForHumanReview`**, use that section here (preferred).

**This section must be fully visible in the chat before any approval UI.**

### 6. Clarifying questions (if any)

Numbered list from story-writer. Optional decisions only — do not bundle approval choices here.

### 7. STOP line (required — end of turn)

End the message with:

```markdown
---
**Review the suggested acceptance criteria above.** Reply on your next message with one of:
- **Approve** — proceed with suggested AC
- **Approve original** — use Jira AC only
- **Edits** — paste revised AC
- **Update Jira first** — you will update the ticket, then we re-fetch
- **Reject** — stop or pick a different ticket

Do not proceed to codebase research or builders until you approve.
```

**End the agent turn here.** Do not invoke tools that advance the factory after this message.

---

## Turn 2 — Approval only

On the **next** user message:

- If the user asked to see AC/deliverables first, or section **5** (Suggested acceptance criteria / Deliverable checklist for human review) was skipped or summarized → **re-run the full presentation turn (sections 1–7)** and **STOP** again (void any earlier approval prompts).
- If the user **Approve** / **Approve original** / **Edits** (with pasted AC or checklist) → merge into **refined story packet** and continue to Step 1 (implementation) or Step A1 (analysis).
- If **Update Jira first** → wait for confirmation or re-fetch.
- If **Reject** → stop; summarize what was explored.

Approval turn may use plain chat or **AskQuestion** — never in the same turn as the first presentation.

---

## Prohibitions (Step 0a presentation turn)

- Do **not** use **AskQuestion** (or any approval picker) in the same turn as story-writer output.
- Do **not** paraphrase or summarize suggested AC — render the **full numbered list**.
- Do **not** launch **`codebase-researcher`**, **`backend-builder`**, **`client-builder`**, **`feature-builder`**, or **`devops-builder`** until explicit human approval on a **later** turn.
- Do **not** treat answers to clarifying questions (e.g. branch name, scope exclusions) as story approval unless the user also approves AC.

---

## Analysis path (`{run_mode}` = analysis)

Same two-turn rule. Use sections **1–7** below — **do not** use the implementation section **7** STOP block.

| Section | Analysis content |
|---------|------------------|
| 1 | Header |
| 2 | Ticket packet |
| 3 | Original Expected Output / deliverables (from Jira) |
| 4 | Story-writer report (StaleOrCompletedScope, ScopeNotes) |
| 5 | **Deliverable checklist for human review** — copy **`DeliverableChecklistForHumanReview`** or **`DeliverableChecklist`** verbatim |
| 6 | Clarifying questions (if any) |
| 7 | Analysis STOP line (below) — **not** the implementation STOP block |

### 7. STOP line — analysis (required — end of turn)

End the message with:

```markdown
---
**Review the deliverable checklist above.** Reply on your next message with one of:
- **Approve** — proceed with deliverable checklist
- **Edits** — paste revised deliverable checklist
- **Update Jira first** — you will update the ticket, then we re-fetch
- **Reject** — stop or pick a different ticket

Do not proceed to deep research until you approve.
```

**End the agent turn here.**

---

## Free-text kickoff (Step 0b)

When `story_writer.run_on_free_text` is true, present story-writer output using the same section order; section 3 may be **(free-text — no Jira AC)**.
