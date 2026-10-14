---
name: retro-feature-interview
description: >-
  Interactive feature interview from an operator retro file; produces spec.md
  alongside retro.md in a named docs/plans/<bundle>/ directory. Use after
  /operator-onboarding-retro when ready to decide scope and acceptance criteria.
---

# Retro feature interview

Follow [the retro-feature-interview skill](../skills/retro-feature-interview/SKILL.md).

## User input

| Field | Source |
|-------|--------|
| `retro_path` | **Required** — `@`-mentioned file or path to `docs/plans/<bundle>/retro.md` or a legacy flat `operator-onboarding-*-retro.md` |
| `focus` | Optional — one investigation, theme, or operator outcome to prioritize |
| `bundle` | Optional kebab-case directory name under `docs/plans/` when creating or renaming a bundle (otherwise propose in the agenda) |

If the user invokes **`/retro-feature-interview`** with only an `@` retro file, treat that path as `retro_path`.

## Procedure

1. Resolve `retro_path`; read the retro fully.
2. Resolve or propose a **plan bundle** directory (see skill): `docs/plans/<bundle>/` with `retro.md` and `spec.md`.
3. If the retro is still a legacy top-level file, include relocation into `<bundle>/retro.md` in the agenda; relocate only after the user confirms the bundle name.
4. Confirm feature boundary, then run the grill-style interview until closure.
5. Present the full draft specification in chat and **stop**.
6. After approval, write `docs/plans/<bundle>/spec.md`, update the bundle `README.md`, and update [docs/plans/README.md](../../../docs/plans/README.md). Do not commit unless requested.
