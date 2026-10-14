---
name: spec-implementation-map
description: >-
  Explore the codebase against an approved plan-bundle spec and publish
  implementation.md with deltas, touchpoints, orchestration packages, and
  verification hooks. Use after /retro-feature-interview when ready to staff
  implement and verify agents.
---

# Spec implementation map

Follow [the spec-implementation-map skill](../skills/spec-implementation-map/SKILL.md).

## User input

| Field | Source |
|-------|--------|
| `spec_path` | **Required** — `@`-mentioned file or path to `docs/plans/<bundle>/spec.md` |
| `focus` | Optional — one decision ID, AC, or workstream to prioritize in exploration |
| `bundle` | Optional kebab-case directory under `docs/plans/` when `spec_path` alone does not resolve the bundle |

If the user invokes **`/spec-implementation-map`** with only an `@` spec file, treat that path as `spec_path`.

## Procedure

1. Resolve `spec_path`; read the spec fully (and linked retro/GWT when referenced).
2. Confirm bundle path: **`docs/plans/<bundle>/implementation.md`** beside `spec.md` (canonical only).
3. If adhoc or dated maps exist in the bundle, plan to **merge** into `implementation.md` and **supersede** the extras.
4. Present a short agenda (scope, focus, artifact path, merge/supersede) and **stop** unless the user already asked to skip confirmation.
5. Explore the repository: present vs required deltas, **strengths (spec)** and **strengths (repository)**, workstreams, **packages P1…Pn** with **package + verifier briefs**, build order (with rationale if needed), tests, and risks.
6. Present the full draft implementation map in chat and **stop**.
7. After approval, write `implementation.md`, update bundle `README.md`, supersede stale maps, align `spec.md` status with README if needed, and update [docs/plans/README.md](../../../docs/plans/README.md) when appropriate. Do not commit unless requested.
