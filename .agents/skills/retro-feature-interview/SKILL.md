---
name: retro-feature-interview
description: >-
  Turn an operator retro file into an interactive feature interview and write
  spec.md next to retro.md under docs/plans/<bundle>/. Use with
  /retro-feature-interview and a retro_path, or when the user wants grill-me
  Q&A from docs/plans/*/retro.md into a draft specification.
disable-model-invocation: true
---

# Retro → feature interview

Convert a **plan bundle** retrospective into a **draft feature specification** through structured back-and-forth with the user. Retros explore options and probes; this skill **chooses** direction with the operator and records scope, decisions, and acceptance criteria in the same directory as the retro.

Do not replace the retro. Do not treat retro "directions to explore" as decided scope until the user confirms in the interview.

## Plan bundle layout

Each feature thread lives under **`docs/plans/<bundle>/`** (kebab-case `bundle` slug):

| File | Purpose |
|------|---------|
| `README.md` | Bundle index: title, status, links to `retro.md`, `spec.md`, and related plans |
| `retro.md` | Operator experience retrospective ([operator-onboarding-retro](../operator-onboarding-retro/SKILL.md)) |
| `spec.md` | Draft feature specification produced by this skill |
| `implementation.md` | Code delta and orchestration map ([spec-implementation-map](../spec-implementation-map/SKILL.md)) |

The interview skill **owns naming and creating** the bundle when the user passes a legacy retro path or a new thread. The retro skill writes `retro.md` into an existing or new bundle.

### Bundle naming

- Short, product-facing kebab-case (e.g. `porcelain-first-run`, `shape-cli-handoff`).
- Derive from retro title, cross-cutting theme, or user `bundle` argument — **propose in the agenda** unless `bundle` was supplied on `/retro-feature-interview`.
- Avoid the `operator-onboarding-` prefix in directory names; that prefix is legacy for flat files only.

### Legacy flat retros

Path pattern: `docs/plans/operator-onboarding-<slug>-retro.md`.

When `retro_path` points at a legacy file:

1. Propose `<bundle>` and relocation to `docs/plans/<bundle>/retro.md`.
2. After the user confirms the bundle name (agenda turn), create the directory, write or update `README.md`, **move** the retro to `retro.md`, and fix repository-relative links (one extra `../` per link depth).
3. Leave a short stub at the old path only if other docs still link there; otherwise remove the legacy file and update [docs/plans/README.md](../../../docs/plans/README.md) links.

If `retro_path` is already `docs/plans/<bundle>/retro.md`, use that `<bundle>` for `spec.md`.

## Relationship to other workflows

| Artifact / workflow | Role |
|---------------------|------|
| [operator-onboarding-retro](../operator-onboarding-retro/SKILL.md) | Writes `retro.md` — **input** |
| This skill | Interview → `spec.md` |
| [spec-implementation-map](../spec-implementation-map/SKILL.md) | Approved spec → `implementation.md` |
| `shape` / `shape.examine` | Optional engine flow after `spec.md` exists |
| [foundry-run-evaluation](../foundry-run-evaluation/SKILL.md) | Run correctness; cite when retro links a run |

## Inputs

Resolve before interviewing:

1. **`retro_path` (required)** — from `/retro-feature-interview` or `@` mention. Read the retro fully.
2. **`bundle` (optional)** — target directory under `docs/plans/`.
3. **`focus` (optional)** — one investigation, cross-cutting theme, or outcome.
4. **Optional seed** — e.g. `spec.md` draft or `docs/plans/foundry-up.md` referenced by the retro; refine, do not treat as final.

## Interview discipline (grill-me style)

- **One turn, few questions:** At most **three** clarifying questions per message unless the user asks for a batch.
- **Why needed:** One sentence on what decision or AC line each question unlocks.
- **Retro grounding:** Name the investigation or probe; quote or paraphrase the operator signal when useful.
- **No silent decisions:** User chooses among retro options and tradeoffs.
- **Deferrals allowed:** Record as `deferred`; do not block on non-material unknowns.
- **No implementation during interview** unless requested; touchpoints belong under implementation hints in `spec.md`.

### Question shape (in chat)

```markdown
**Q1 (`<slug>`):** <question>
- *Why:* <what changes in scope or AC>
- *From retro:* <investigation title or cross-cutting line>
```

After answers, record **decisions** and **assumptions** before the next batch.

## Phases

### 1. Ingest and confirm scope

- Resolve bundle location; create directory and relocate legacy retro when confirmed.
- Produce a short **agenda**: feature title, bundle path, retro sections in scope, explicit out-of-scope, operator outcome.
- **Stop** after the agenda until the user confirms boundary and bundle name (unless both were supplied up front).

### 2. Interview loop

Repeat until **closure**:

- Prioritize investigations marked **open** (or **mitigated** when specifying residual UX).
- Work cross-cutting themes that span investigations.
- Turn retro probes into **verification** scenarios once decisions exist.
- Prefer the user's current intent over stale retro text; note historical context.

### 3. Closure criteria

- In / out of scope are explicit.
- Must-ship behavior has testable acceptance criteria.
- Material tradeoffs have a recorded **decision**.
- No open questions would materially change scope or AC.

### 4. Present specification (presentation turn)

Render the full draft in chat using the [output template](#output-template). **Stop.** No file writes in this turn.

### 5. Publish (decision turn)

After explicit approval or directed edits:

- Write `docs/plans/<bundle>/spec.md`.
- Update `docs/plans/<bundle>/README.md` (link `spec.md`, status line).
- Update [docs/plans/README.md](../../../docs/plans/README.md) open-work table (bundle row, not only loose files).

Commit only when requested.

### Bundle README template

```markdown
# <Title>

Status: **open** — retro investigation; spec <draft | none>.

| Artifact | Description |
|----------|-------------|
| [retro.md](retro.md) | Operator experience and design investigation |
| [spec.md](spec.md) | Draft feature specification (after `/retro-feature-interview`) |
| [implementation.md](implementation.md) | Implementation map (after `/spec-implementation-map`) |
```

## Output template (`spec.md`)

Adapt sections; omit empty ones. Link to [retro.md](retro.md) in **Source** instead of duplicating investigations.

```markdown
# <Feature title>

Status: **draft specification** — from operator retro interview (<date>).

## Source

- Bundle: [README](README.md)
- Retro: [retro.md](retro.md) — investigations: …

## Operator outcome

…

## Problem statement

…

## Scope

### In scope

- …

### Out of scope

- …

## Decisions

| ID | Decision | Rationale | Retro link |
|----|----------|-----------|------------|
| D1 | … | … | §… |

## Assumptions

- …

## Acceptance criteria

1. …

## Verification plan

- …

## Implementation hints (optional)

- …

## Deferred / follow-up

- …
```

For CLI-shaped features, a **Given / When / Then** block (see [foundry-up.md](../foundry-up.md)) may supplement acceptance criteria.

## Anti-patterns

- Publishing `spec.md` outside the retro's bundle directory.
- Dumping every retro probe in one message.
- Copying "directions to explore" as committed design without user choices.
- Merging unrelated investigations without an explicit boundary conversation.
- Auditing steward advice from the retro session.

## Command entrypoint

[`.cursor/commands/retro-feature-interview.md`](../../commands/retro-feature-interview.md) — requires `retro_path` (typically via `@` file on invoke).
