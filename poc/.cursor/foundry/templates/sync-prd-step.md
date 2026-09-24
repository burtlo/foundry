# Ensure PRD sync caller workflow (foundry / documentation-workflow)

Run in **`{app_folder}`** after PRD generation (documentation-workflow Steps 7a–7c) and **before Step 8 developer review**.

Ensures merged PRDs sync to `ORG/factory/prds/` via the org reusable workflow.

---

## When to run

| Condition | Action |
|-----------|--------|
| `.github/workflows/sync-prd.yml` **missing** | **Create** from org template (Step 2 — never hand-write) |
| File **exists** | Verify + fix drift (Step 2b); re-copy from template if multiple issues |
| File **exists** but **no `permissions:` block** | **Update** — re-copy template or insert block before `jobs:` |
| PRD generated or updated in this run | **Always** run Steps 1–5 (including validation gate) |

**Mandatory** in implement.documentation and full documentation-workflow when a PRD is created or updated.

---

## Caller checklist (intent — scripts implement this)

The file `.github/workflows/sync-prd.yml` in `{app_folder}` must:

1. Exist (app-repo **caller**, not the org reusable workflow).
2. Have a top-level `permissions:` block with `contents: read` **immediately before** `jobs:`.
3. Call `ORG/factory/.github/workflows/sync-prd.yml@main`.
4. Pass `O_GH_REPOSITORY_TOKEN` to the reusable workflow.
5. **Not** pass `O_AZURE_PRD_BLOB_CONNECTION_STRING` or `O_AZURE_SEARCH_ADMIN_KEY`.

If the file starts with `on:` and also contains `workflow_call:`, it is the org reusable workflow — do not treat it as a caller.

---

## Step 1 — Check for caller workflow

Look for `.github/workflows/sync-prd.yml` under `{app_folder}`. Report `exists` or `missing`.

---

## Step 2 — Create from org template (when missing or heavily drifted)

**Read the entire template and Write it to the app repo — do not hand-write YAML and do not `cp` / `Copy-Item`.**

Resolve factory root (`{org_repo_path}`) per `WORKSPACE.md` / foundry variables contract (§7). Template path:

`{org_repo_path}/.cursor/foundry/templates/sync-prd-caller.yml`

Write that content to `{app_folder}/.github/workflows/sync-prd.yml` (create `.github/workflows/` if needed).

**Canonical source:** `.cursor/foundry/templates/sync-prd-caller.yml` in the plugin bundle or `github-private` clone.

Do **not** hand-edit the reusable workflow in `.github-private` — only add the thin caller in the app repo.

**Required shape** (must match template):

```yaml
permissions:
  contents: read

jobs:
  sync:
    uses: ORG/factory/.github/workflows/sync-prd.yml@main
    secrets:
      O_GH_REPOSITORY_TOKEN: ${{ secrets.O_GH_REPOSITORY_TOKEN }}
```

---

## Step 2b — Fix permissions when caller exists but is incomplete

Read `.github/workflows/sync-prd.yml` and apply the **Caller checklist**. When **permissions missing** or **Azure secrets present on caller**, prefer **re-copying the template** (Step 2). Otherwise insert:

```yaml
permissions:
  contents: read
```

immediately before `jobs:`. Report status as **`updated`**.

---

## Step 3 — Document in root AGENTS.md

Add or update the **CI/CD** workflows table in root `AGENTS.md`:

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| **PRD Sync** | `sync-prd.yml` | `push: main/master` (PRD path changes) | Sync PRD to `ORG/factory/prds/` |

Note in CI/CD or Security section that the caller uses **`permissions: contents: read`** (explicit GITHUB_TOKEN scope).

---

## Step 4 — Report to parent

Return:

- **sync-prd.yml** — `created` | `already present` | `updated`
- **sync-prd permissions** — `present` | `added` (must be `permissions:\n  contents: read` before `jobs:`)
- **AGENTS.md CI/CD row** — added | already documented
- **Prerequisite note** — source repo needs org secret `O_GH_REPOSITORY_TOKEN` (one-time infra; not blocked on missing secret for file creation). Foundry Azure secrets stay on `.github-private` only.

---

## Step 5 — Validation gate (required — do not skip)

**Run before returning DocChangeReport or proceeding to Step 8 developer review.**

From **`{app_folder}`** (resolve factory root first). Run **only** the command for the current shell:

```text
powershell -NoProfile -File "{org_repo_path}/.cursor/foundry/scripts/validate-sync-prd-caller.ps1"
```

```text
bash "{org_repo_path}/.cursor/foundry/scripts/validate-sync-prd-caller.sh"
```

If the script **fails**, fix the file (re-copy template) and re-run until **exit 0**. Treat failure as a **blocker** — do not claim Step 7 complete.

**Why this exists:** Step 7b PRD validation (40 checks) runs **before** this file is created and does **not** inspect workflow YAML. This gate is the only automated check for caller correctness.

---

## Org prerequisites (informational — do not block file creation)

Document in PR or Step 8 summary if the team may need to verify:

1. `ORG/factory` reusable workflow exists at `.github/workflows/sync-prd.yml`
2. Org/repo secret `O_GH_REPOSITORY_TOKEN` on the **app repo**
3. App repo Actions can call reusable workflows from `.github-private`

See **documentation-workflow.md** → “CI/CD Integration: Organization PRD Sync”.
