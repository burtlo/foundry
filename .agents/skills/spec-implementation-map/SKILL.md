---
name: spec-implementation-map
description: >-
  Compare an approved plan-bundle spec to the current codebase and publish
  implementation.md with deltas, touchpoints, work packages, and verification
  hooks for orchestrator-led implement and verify agents. Use after
  /retro-feature-interview with /spec-implementation-map and spec_path.
---

# Spec → implementation map

Produce **`docs/plans/<bundle>/implementation.md`**: the **single canonical** delta between **what the spec requires** and **what the repository already implements**, with enough structure that an **orchestrator agent** can assign **implementer** and **verifier** agents without re-reading the whole codebase.

This skill does **not** implement features. It **explores**, **records gaps**, and **packages work**. Treat [spec.md](spec.md) as normative; the map is the bridge to coordinated execution.

**Do not** publish parallel “implementation map” files as co-equal artifacts. If an adhoc or dated map already exists, **merge** useful content into `implementation.md`, then mark the old file **superseded** (banner + link to canonical) or remove it when the operator directs.

## Plan bundle layout

Each feature thread lives under **`docs/plans/<bundle>/`**:

| File | Purpose |
|------|------|
| `README.md` | Bundle index and status; must point to **one** canonical `implementation.md` |
| `retro.md` | Operator experience ([operator-onboarding-retro](../operator-onboarding-retro/SKILL.md)) |
| `spec.md` | Approved feature specification ([retro-feature-interview](../retro-feature-interview/SKILL.md)) |
| `implementation.md` | **This skill** — code map, deltas, work packages, build order, verifier briefs |
| `gwt-scenario.md` | Optional Given/When/Then seed referenced by the spec |

If `spec_path` is `docs/plans/<bundle>/spec.md`, use that `<bundle>` for `implementation.md`.

## Relationship to other workflows

| Artifact / workflow | Role |
|---------------------|------|
| [retro-feature-interview](../retro-feature-interview/SKILL.md) | Writes `spec.md` — **input** |
| This skill | Explores codebase → `implementation.md` |
| `shape` / `execute` | Engine flows; may consume bundle artifacts as input |
| Orchestrator + implementer agents | Execute **packages P1…Pn** from the map |
| Verifier agents | Prove packages using **verifier briefs**, AC, tests, and verification plan in spec |

## Inputs

Resolve before exploring:

1. **`spec_path` (required)** — from `/spec-implementation-map` or `@` mention. Read the spec fully (scope, decisions, AC, verification plan, implementation hints).
2. **`bundle` (optional)** — when `spec_path` is ambiguous or legacy; otherwise derive from directory.
3. **`focus` (optional)** — one decision ID, AC range, or workstream to prioritize (still produce a full map unless user asks for a partial update).
4. **Optional context** — `retro.md`, `gwt-scenario.md`, prior `implementation.md`, or adhoc maps; **merge and re-verify** against the repo. Stale maps are not ground truth.

## Exploration discipline

- **Spec-first:** Every work package and delta row links to a **decision ID**, **AC number**, or explicit **spec section**.
- **Evidence in repo:** Cite paths with **clickable relative links** from the bundle to source (e.g. `../../../.cursor/foundry/cli/...`) plus a **repository layout** path table. Name entrypoints (commands, modules, tests, docs). Distinguish **verified current behavior** from **inference**.
- **Delta language:** Gaps table columns are **Present state | Spec requirement | Suggested resolution** (all three required per row). Mark **partial** in AC traceability when behavior exists but does not meet AC.
- **Two strength lenses:** Under **Spec alignment**, include **Strengths (spec)** (why the spec is buildable) and **Strengths (repository)** (what already aligns in code). Do not substitute a spec-quality review for repo exploration.
- **Surfaces:** Tag each package touchpoint: `code` | `cli-ui` | `host-ui` | `config` | `docs` | `tooling` | `ci`.
- **No silent scope:** Clarifications discovered during exploration go in **Gaps and clarifications** — not as hidden assumptions in packages.
- **Orchestrator-ready packages:** Each package must be **assignable in isolation** where possible, with **depends on**, **deliverables**, and **verify** hooks. **Workstreams alone are insufficient** — every in-scope AC must map to at least one package ID in the traceability table.
- **Verification realism:** Note **CI constraints** (credentials, live vs mocked paths), **platform** matrix (e.g. win32 vs unix), and **fixture path mismatches** (GWT vs AC paths) in gaps or cross-cutting risks.
- **Build-order conflicts:** When the spec defines multiple surfaces (e.g. readiness on command A vs status on command B), add a short **Build order rationale** under suggested order — do not bury the decision only in narrative workstreams.

### When the spec is not ready

If scope, AC, or material decisions are still open, **stop** after a short readiness note in chat. Point the operator to `/retro-feature-interview` or spec edits. Do not publish a full map on a draft spec unless the user explicitly requests a **preview map** (status: `preview — spec incomplete`).

When publishing after approval, align **`spec.md` status** with bundle `README.md` (e.g. approved date) if they disagree.

## Phases

### 1. Ingest and agenda

- Resolve bundle; read `spec.md`, skim `retro.md` / `gwt-scenario.md` when linked.
- Note existing `implementation.md` or adhoc maps to merge.
- Produce a short **agenda**: bundle path, spec status, in-scope AC/decisions for this pass, exploration depth (full tree vs `focus`), expected artifact path, and whether prior maps will be superseded.
- **Stop** after the agenda until the user confirms boundary (unless `spec_path` and full pass were supplied with explicit “publish without agenda”).

### 2. Repository exploration

- Trace each in-scope AC and decision to current CLI, host, bridge, workflow, docs, and tests.
- Record **strengths (spec)** and **strengths (repository)** and **gaps** (missing, wrong, or incomplete).
- Identify **prerequisites** not labeled in the spec (e.g. discovery file before a command exists).
- Note **platform**, **CI**, **breaking-change**, and **secrets** risks with mitigation.

### 3. Package for orchestration

- Group work into **packages** with IDs `P1`, `P2`, … (implementer-sized).
- Populate the **Orchestration packages** table: Title, Surfaces, Depends on, Primary paths, Verify (AC / tests).
- Write **Package briefs** (goal, deliverables, out of scope, touchpoints) for **every** package.
- Write **Verifier briefs** (must prove, commands/probes, regression watch) for **every** package — at minimum P1 and the highest-risk packages; thin briefs are acceptable only when verification is fully delegated to an AC row and named tests.
- **AC traceability:** `Present | Delta / work` with **package IDs** (e.g. **P4**) in the Delta column.
- Produce **suggested implementation order** (package sequence) respecting dependencies and spec **order gates** (e.g. ship D3 before `up`).
- Add **Build order rationale** when two decisions could be sequenced either way.

### 4. Present map (presentation turn)

Render the full draft in chat using the [output template](#output-template). **Stop.** No file writes in this turn.

### 5. Publish (decision turn)

After explicit approval or directed edits:

- Write `docs/plans/<bundle>/implementation.md` (overwrite canonical; status **`ready for orchestration`** when complete).
- Update `docs/plans/<bundle>/README.md` — one canonical map link; artifact table row for `implementation.md`.
- Supersede adhoc/dated maps: banner at top pointing to `implementation.md`, status **archived**.
- Update [docs/plans/README.md](../../../docs/plans/README.md) open-work table when status changes (e.g. “implementation map ready”).

Commit only when requested.

### Bundle README snippet (after map exists)

```markdown
| [implementation.md](implementation.md) | **Canonical** — deltas, work packages (P1–Pn), verifier hooks, build order |
```

## Output template (`implementation.md`)

Adapt sections; **do not omit** Orchestration packages, Package briefs, or Verifier briefs for a full pass. Link to [spec.md](spec.md) in the header; do not duplicate full AC text — trace by ID/number.

```markdown
# <Feature title> — implementation map

Status: **ready for orchestration** — companion to [spec.md](spec.md). Canonical map for implementer assignment and verifier checklists. Refresh with `/spec-implementation-map @spec.md` after material spec or code changes.

## Spec alignment

### Strengths (spec)

- …

### Strengths (repository)

- …

### Gaps and clarifications before build

| Topic | Present state | Spec requirement | Suggested resolution |
|-------|---------------|------------------|----------------------|
| … | … | … | … |

### Acceptance criteria traceability

| AC | Present | Delta / work |
|----|---------|----------------|
| 1 | … | **P1** … |

---

## Repository layout

Short paragraph plus **path anchors** table (role + link to source).

---

## Workstreams mapped to decisions

### <Decision id> — <short title>

**Present:** …

**Required:** …

| Resource | Role |
|----------|------|
| [module.py](../../../path/to/module.py) | … |

**Risks:** …

(Repeat per decision or logical workstream.)

---

## Orchestration packages

| ID | Title | Surfaces | Depends on | Primary paths | Verify (AC / tests) |
|----|-------|----------|------------|---------------|---------------------|
| P1 | … | code, cli-ui | — | … | AC …; `tests/…` |

### Package briefs (for implementer agents)

#### P1 — <title>

- **Goal:** …
- **Deliverables:** …
- **Out of scope:** …
- **Touchpoints:** …

(One subsection per package.)

### Verifier briefs

#### P1 — verification

- **Must prove:** …
- **Commands / probes:** …
- **Regression watch:** …

(One subsection per package.)

---

## Suggested implementation order

**Canonical package sequence:** P1 → P2 → …

### Build order rationale

(When needed: explain sequencing between related decisions/surfaces.)

1. …

---

## Test and fixture resources

| Asset | Use |
|-------|-----|
| … | … |

(Optional: **CI** — live vs mocked paths.)

---

## Cross-cutting risks summary

| Risk | Severity | Mitigation |
|------|----------|------------|
| … | … | … |

---

## Related artifacts

- [spec.md](spec.md)
- [retro.md](retro.md)
- …
```

**Reference example (foundry-up):** [docs/plans/foundry-up/implementation.md](../../../docs/plans/foundry-up/implementation.md) — merged map with P1–P10, dual strengths, build-order rationale (e.g. `up` readiness before `host status` refactor when spec splits surfaces).

## Anti-patterns

- Publishing `implementation.md` outside the spec's bundle directory.
- **Workstreams without orchestration packages** — orchestrators cannot staff verify agents from decision sections alone.
- **Gaps table with only “Issue”** (or narrative bullets) instead of **present | required | resolution**.
- **AC table that only lists files/surfaces** without Present/Delta and package IDs.
- **Spec-review-only strengths** with no repository strengths or path evidence.
- Listing files without stating present vs required behavior.
- Packages with no verifier brief or AC traceability.
- Multiple co-equal implementation maps in one bundle without a superseded archive.
- Treating retro probes as committed scope without spec backing.
- Implementing product code during mapping unless the user explicitly requests a spike documented in the map.
- Duplicating the entire spec or retro in the map.

## Command entrypoint

[`.cursor/commands/spec-implementation-map.md`](../../commands/spec-implementation-map.md) — requires `spec_path` (typically via `@` file on invoke).
