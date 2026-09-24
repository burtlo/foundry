# Factory documentation workflow (implement.documentation)

Run in **`{app_folder}`** after **Step 6 code review approval** and gated **Steps 7b / 7c** (when those gates are on), and **before the Pre-Step-8 gate checklist and Step 8**.

**Mandatory on every implementation-path run.** Never skip—even for framework-only, **devops-only**, **workflow-only**, or docs-only-looking changes.

**If you cannot point to a completed `DocChangeReport` from this run, do not proceed to the Pre-Step-8 gate checklist or Step 8.**

**Delegation:** implement.documentation launches subagent **`documentation-writer`**, which follows this file. The **parent** still runs the human approval gate.

Select the path from snapshot **`documentation.model`** (and pipeline **`workflow`** when present). Registered factory-shipped models: **`iot-agents-prd`**, **`feature-records`**. Unknown models fail before run creation. Do not invent a plugin loader.

---

## When to run (every model)

| Step | Activity |
|------|----------|
| Step 6 | Code review — human approves **implementation** changes |
| **Step 7b** | **devops-builder** `pre_pr_review` — SHA pin/refresh scan — when `devops.enabled` and `devops.run_before_pr` — human approves workflow diff |
| **Step 7c** | **Pre-PR Cursor review** — Bugbot + Security (`review.enabled` and `review.run_before_pr`; default `review.mode: both`) — human approves findings; fixes go back to builders, not docs |
| **Step 7 (this file)** | Documentation for the selected model — after the critic cycle — human approves docs |
| Step 8 | Single commit (feature + docs + workflows) → PR → Jira |

### Forbidden skip reasons

These are **not** valid reasons to skip Step 7 or to mark documentation "N/A" in the PR body:

- Ticket is GitHub Actions pinning / CI / DevOps only
- `devops-builder` already changed workflows at factory Step 4
- Diff is small, YAML-only, or copied from a sibling repo
- User approved the story packet but not the documentation gate
- Feature records or AGENTS.md already looked complete without a DocChangeReport this run

### Inputs from parent

Pass into the workflow:

- Snapshot `documentation.model` and pipeline `workflow`
- Approved technical brief and story/AC (or ticket packet)
- Builder summary(ies), validator report, and Step 7c ReviewChangeReport when Step 7c ran
- `{app_folder}` scope only

---

## Model: `iot-agents-prd`

Follow the full org documentation workflow end-to-end:

**`{factory_root}/.cursor/commands/documentation-workflow.md`**

Resolve via `{factory_root}/.cursor/commands/documentation-workflow.md` or `templates.documentation_workflow` in team-variables.

Also use:

- `{factory_root}/.cursor/commands/templates/agents-md-templates.md`
- `{factory_root}/.cursor/commands/templates/prd-generator-template.md`

When `templates.update_docs` / `templates.generate_prd` exist in team-variables, treat them as supplements—not a substitute for the full workflow.

The parent still runs human approval (documentation-workflow Step 8).

### Mode selection (skip interactive mode prompt)

Do **not** ask the developer to pick Full / Audit / Update at workflow start. Auto-select:

| Repo state | Mode |
|------------|------|
| No root `AGENTS.md` | **Full Workflow** (Steps 1–8) |
| Root `AGENTS.md` exists | **Update Existing** (audit gaps, update/create entry-point docs, refresh PRD) |

Never use **Audit Only** in foundry (audit is embedded in Update Existing / Full Workflow).

No root `AGENTS.md` is not a skip — use **Full Workflow** (create it).

### Steps to execute

Run **documentation-workflow** through:

1. Step 1 — Discover solution structure (confirm entry points with human if unclear)
2. Step 2 — Audit existing AGENTS.md completeness
3. Step 3 — Auto-discover metadata (IoT defaults; confirm unknowns with human at Step 3d)
4. Steps 4–5 — Create/update root and entry-point AGENTS.md
5. Step 6 — Create or update PRD generator
6. Step 7 — Generate PRD (7a), **Step 7b validation**, **Step 7c PRD confirmation**
7. **Step 7d** — PRD sync caller — follow **`sync-prd-step.md`**: Read+Write `sync-prd-caller.yml` when missing/drifted; run **`validate-sync-prd-caller.ps1`** (Windows) or **`.sh`** (macOS/Linux) (exit 0 required)
8. **Step 8 — Developer review** — **mandatory human gate**

**Skip documentation-workflow Step 9 (commit).** Factory Step 8 commits feature code and documentation together.

Use brief/builder context to pre-fill metadata and highlight sections that changed (e.g. framework version, CI SDK, new integrations).

### PRD rules

- **Always** create or update `Documentation/prd-generator-prompt.md` when missing or incomplete.
- **Always** generate/regenerate PRD after AGENTS.md changes in this run.
- **Always** run Step 7b validation; fix source AGENTS.md or regenerate until validation passes or human accepts documented gaps.
- **Always** run **Step 7d** (`sync-prd-step.md`) after Step 7c: Read+Write `sync-prd-caller.yml` (never hand-write); run **`validate-sync-prd-caller.ps1`** (Windows) or **`.sh`** (macOS/Linux) before DocChangeReport.

`docs discover`, `docs audit`, `prd generate`, and `prd validate` are IoT backend CLI helpers. The parent does not run them; the IoT workflow may still use them.

### Human gates (parent presents)

1. Entry point discovery (workflow Step 1d) — if ambiguous
2. Metadata confirmation (workflow Step 3d) — required when unknown fields remain
3. **Developer review (workflow Step 8)** — **required before Step 8 delivery**

Reply **approved** to proceed to the **Pre-Step-8 gate checklist**, or **request changes** with specifics.

### Report to parent (`iot-agents-prd`)

Return **DocChangeReport**:

- **Model** — `iot-agents-prd`
- **AGENTS.md files touched** — list paths (root + entry points)
- **PRD generator** — created/updated/skipped with path
- **PRD path** — generated file path
- **sync-prd.yml** — created | already present | updated
- **sync-prd validation** — `validate-sync-prd-caller.ps1` / `.sh` pass | fail (fail = blocker)
- **Validation** — Step 7b pass/fail summary
- **Blockers** — anything preventing Step 8 delivery

### Legacy template keys

`templates.update_docs` and `templates.generate_prd` in team-variables remain valid references for documentation-writer when resolving org templates; they do **not** replace the full documentation-workflow for this model.

---

## Model: `feature-records`

Feature records only. Do **not** run `documentation-workflow`. Do **not** look for `.sln` / `.csproj`. Do **not** create AGENTS.md IoT metadata tables. Do **not** generate `Documentation/prd-*-generated.md`. Do **not** add `sync-prd.yml`. Publication is **not** required.

Update `docs/features` records (and linked as-built notes) so they match shipped behavior.

1. Identify shipped behavior vs the draft/active plan. Verify in code.
2. Prefer updating an existing `docs/features/` record. If none fit, add one and a README row.
3. Distill invariants, interfaces, code map, and operator-visible behavior — do not paste full plan prose.
4. If a plan shipped, set plan front-matter **As-built** to the feature path(s); do not document unshipped phases as current.
5. **Skip commit.** Factory Step 8 commits feature code and documentation together.
6. **Developer review** — **mandatory human gate** (DocChangeReport). "Nothing changed" is still a DocChangeReport.

### Human gates (parent presents)

**Developer review** — **required before Step 8 delivery**. Reply **approved** to proceed, or **request changes** with specifics.

### Report to parent (`feature-records`)

Return **DocChangeReport**:

- **Model** — `feature-records`
- **Feature records touched** — list paths or "none"
- **As-built plan links** — set | already set | N/A
- **Summary of changes** — bullet per file (or "nothing changed")
- **Publication** — not required
- **Blockers** — anything preventing Step 8 delivery
