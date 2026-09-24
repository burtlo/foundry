# Generate PRD from AGENTS.md Files

**ALWAYS generate/update the PRD after updating AGENTS.md files. This step is mandatory.**

**Reference:** PRD templates are centralized in `templates/prd-generator-template.md`

---

## Check for PRD Generator

Check if a PRD generator prompt exists in the solution. Look for:
- `Documentation/prd-generator-prompt.md`
- `documentation/prd-generator-prompt.md`
- `docs/prd-generator-prompt.md`

---

## If PRD Generator EXISTS - Check for Updates

**Important:** The organizational PRD template may have been updated with new sections. Check if the existing PRD generator needs updating.

### Required PRD Sections (Current Template)

The PRD generator should produce these sections:
1. System Identity
2. Technical Architecture
3. External Interfaces
4. Data Architecture (includes Store Data Scope and Environment Data Replication subsections)
5. Security & Compliance
6. Component Architecture
7. User Workflows
8. Deployment & Infrastructure
9. **Testing & Quality Assurance** ← Added January 2026
10. Appendices

### Update Check

Scan the existing PRD generator for missing sections:

Scan `Documentation/prd-generator-prompt.md` for missing sections: Testing & Quality Assurance / Test Harness, Store Data Scope, Environment Data Replication.

**If any required sections are missing:**
1. Note which sections need to be added
2. Update the PRD generator file by adding the missing section templates from `templates/prd-generator-template.md`
3. Preserve any solution-specific customizations (Mermaid diagrams, file paths, custom sections)

### Sections to Add if Missing

**Testing & Quality Assurance (Section 9):**
```markdown
## 9. Testing & Quality Assurance

### 9.1 Test Project Inventory
| Component | Test Project | Type | Purpose |
|-----------|--------------|------|---------|
{Combine from all AGENTS.md ## Test Harness & Dev Tools > Test Projects}

### 9.2 E2E Test Integration
{Extract from entry point AGENTS.md ## Test Harness & Dev Tools > E2E Integration}

### 9.3 Test Utilities
{Combine from all AGENTS.md ## Test Harness & Dev Tools > Test Utilities}

### 9.4 Test Data Setup
{Extract from AGENTS.md ## Test Harness & Dev Tools > Test Data Setup}
```

Also add to Extraction Rules table if missing:
```markdown
| `## Test Harness & Dev Tools` | Test projects, E2E selectors, test utilities, test data setup |
```

**Store Data Scope (Section 4.4 under Data Architecture):** ← Added March 2026
```markdown
### 4.4 Store Data Scope
{Extract from root AGENTS.md ## Store Data Scope}

| Field | Value |
|-------|-------|
| **Store Data Source(s)** | {From root AGENTS.md Store Data Scope} |
| **Store Scope** | {All stores / Filtered subset} |

#### Inclusion Rules
| Rule Type | Value | Mechanism |
|-----------|-------|-----------|
{From root AGENTS.md Store Data Scope > Store Inclusion Rules}

#### Exclusion Rules
| Rule Type | Value | Mechanism |
|-----------|-------|-----------|
{From root AGENTS.md Store Data Scope > Store Exclusion Rules}
```

Also add to Extraction Rules table if missing:
```markdown
| `## Store Data Scope` | Store data sources, inclusion rules, exclusion rules, filtering mechanisms |
```

**Environment Data Replication (Section 4.5 under Data Architecture):** ← Added June 2026
```markdown
### 4.5 Environment Data Replication
{Extract from root AGENTS.md ## Environment Data Replication}

| Aspect | Detail |
|--------|--------|
| **Purpose** | {From root AGENTS.md} |
| **Environments** | Non-production only |
| **Trigger** | {Admin route and/or API endpoints} |

#### Orchestration Stages
{From root AGENTS.md > Orchestration Stages table — or "Not Applicable"}

#### Replicated Production Data
{From root AGENTS.md > Replicated Production Data table — or "Not Applicable"}

#### Configuration Gates
{From root AGENTS.md > Configuration Gates table — key names only — or "Not Applicable"}

#### Status & Notifications
{From root AGENTS.md — or "Not Applicable"}

*Cross-reference PRD User Workflows §6.4 when entry points document Environment Data Refresh.*
```

Also add to Extraction Rules table if missing:
```markdown
| Root `## Environment Data Replication` | PRD §4.5 — purpose, scope, orchestration stages, replicated entities, config gates, status, notifications; or Not Applicable |
| `## User Workflows` > Environment Data Refresh | PRD §6.4 — sequence diagram, status endpoint, stage names; cross-ref §4.5 |
```

If root AGENTS.md has no `## Environment Data Replication` section, add the section with **Not Applicable** per `templates/agents-md-templates.md` before regenerating the PRD.

---

## If PRD Generator Does NOT Exist

Create it using the template from `templates/prd-generator-template.md`:

### 1. Create the Documentation folder if needed:

Create the `Documentation/` folder if it does not exist.

### 2. Create the PRD Generator File

Create `Documentation/prd-generator-prompt.md` using the PRD Generator Prompt File Template from `templates/prd-generator-template.md`, customized with:
- Application name from the root AGENTS.md
- List of all AGENTS.md file paths
- Mermaid diagram customized for the solution's architecture
- Correct output path for the generated PRD

---

## Execute PRD Generation

**Read the PRD generator prompt file and execute its instructions:**

1. **Read all AGENTS.md files** in the solution:
   - Root `AGENTS.md`
   - All entry point AGENTS.md files (identified in Step 3a)

2. **Consolidate the information** following the PRD template in the generator

3. **Generate/update the PRD file** (typically `Documentation/prd-{SolutionName}-generated.md`)

4. If the solution has a specific PRD generator with different output paths or formats, follow those instructions instead

---

## Confirmation

**After generating:**

> "I've generated/updated the PRD at `{prd-file-path}`. This will be included in the commit. After merge to `master`/`main`, `sync-prd.yml` copies it to `ORG/factory/prds/{AppName}/`."

---

## Ensure PRD sync workflow (Step 7d)

**After PRD generation and validation**, follow **`{factory_root}/.cursor/foundry/templates/sync-prd-step.md`**:

1. If `.github/workflows/sync-prd.yml` is **missing** or **drifted**, Read+Write (do not hand-write) from **`sync-prd-caller.yml`** (factory root / plugin bundle)
2. From the app repo (`{app_folder}`), resolve **`{org_repo_path}`** and run `validate-sync-prd-caller.ps1` (Windows) or `.sh` (macOS/Linux) — must exit 0
3. If the file **exists** but validation fails, re-copy the template (Step 2b in sync-prd-step.md)
4. Add **PRD Sync** row to root `AGENTS.md` CI/CD table if not present
5. Include `sync-prd.yml` in the factory commit when newly created or updated

**Mandatory** in implement.documentation and full documentation-workflow runs.

---

## Proceed to Developer Review

After PRD generation and sync-prd setup, proceed to **documentation-workflow Step 8** (developer review)—not directly to commit in factory runs.

