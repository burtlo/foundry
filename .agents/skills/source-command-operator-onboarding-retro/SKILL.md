---
name: "source-command-operator-onboarding-retro"
description: "Capture operator feedback as a product design investigation in a plan bundle (docs/plans/<bundle>/retro.md). Use for onboarding or dogfooding retros; /evaluate-run owns run assessment."
---

# source-command-operator-onboarding-retro

Use this skill when the user asks to run the migrated source command `operator-onboarding-retro`.

## Command Template

# Operator onboarding retro

Follow [the operator-onboarding-retro skill](../skills/operator-onboarding-retro/SKILL.md).

## User input

| Field | Source |
|-------|--------|
| `bundle` | Optional kebab-case name for `docs/plans/<bundle>/` (propose one in chat if omitted) |
| `title` | Optional human title for the bundle `README.md` |
| `run_path` | Optional `.foundry/runs/{run_id}` or archive path |

Use the current conversation as the source of the operator's experience. Answer any immediate workflow question, then ask what the need for that answer reveals about the product. Trace material friction to implementation and documentation entrypoints. Explore design alternatives and tradeoffs for each feedback item.

If `run_path` is supplied, record its ID/path and the state relevant to the experience. Link an `/evaluate-run` output in the repository or chat; if none exists, write exactly **“evaluate-run not run—engine verdict omitted.”** Do not create a second run scorecard in the retro.

Create or update `docs/plans/<bundle>/retro.md` and the bundle `README.md`; update the plans index. Do not commit unless requested.
