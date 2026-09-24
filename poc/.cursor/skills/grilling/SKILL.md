---
name: grilling
description: >-
  Foundry intake grilling — design-tree frontier rounds to resolve ambiguity before
  AC freeze. Uses codebase-researcher fact spikes, max_rounds from team profile,
  and emits a structured agent receipt. Invoked from intake.grill only.
disable-model-invocation: true
---

# Grilling (Foundry intake)

**Invoked by the Foundry parent** at `intake.grill` only. Read FactoryConfig from the parent prompt (`config get --role story-writer` includes `grilling.*`).

## Controls (v2)

| Control | Rule |
|---------|------|
| Round cap | `foundry.grilling.max_rounds` (default 2) |
| Frontier only | Batch independent questions per round; defer dependent ones |
| Fact delegation | Narrow `codebase-researcher` spikes — not full Step 1 research |
| No action until confirm | Parent gates at `intake.approve_ac`; you do not approve scope |
| Assumptions | Forbidden in your output — emit **decisions** with explicit text |

**Skip:** Parent skips this step when `readiness == Ready` and `clarifying_questions_count == 0`. Do not run if skipped.

## Procedure

1. Read `draft_ac`, open questions from story-writer, and `risk_tier`.
2. For up to `max_rounds` rounds:
   - Identify the **frontier**: questions answerable without pending upstream answers.
   - For facts needing repo evidence, launch **`codebase-researcher`** with a **narrow** prompt (one pattern, one area). Attach child receipt IDs.
   - Do **not** ask the human — parent collects answers at the grill gate.
   - Record hypotheses (`accepted` / `rejected` / `unresolved`) and settled **decisions**.
3. Emit questions still unresolved as `questions_generated` with `deferred: true` when blocked on other answers.
4. Write the craft overlay to `craft_staging_path` (see below).
5. Return a short alignment summary for the parent grill gate.

## Agent receipt (required)

The parent provides **`craft_staging_path`** from `worker launch-packet`. You **must**:

1. Write schema-valid protocol `2.0.0` craft JSON to that path only. **Never** write under `{run_dir}/receipts/` or edit `.meta.json`.
2. Include only craft fields; receipt/run/launch/step/agent/mode identity is engine-owned.
3. Fill `exploration`, `decisions`, `outputs`, and `recommended_next_state` from the alignment work above.
4. Reply to the parent with **only the staging path** as your final line.

| Field | Source |
|-------|--------|
| `exploration.questions_generated` | Unresolved and deferred questions (`text`, `why`, `deferred`) |
| `exploration.hypotheses` | Settled hypotheses (`text`, `status`, `reason`) |
| `decisions` | Explicit decisions (`text`, `confidence`) |
| `outputs.summary_markdown` | Short alignment summary for the grill gate |
| `recommended_next_state` | `intake.present_ac` or `BLOCKED_ambiguity` |
| `status` | `completed` unless blocked |

For narrow `codebase-researcher` fact spikes: launch via the parent-generated packet and attach completed child receipt IDs when the schema allows.

## Prohibitions

- Do not edit Jira, create branches, or launch builders.
- Do not exceed `max_rounds`.
- Do not bury unresolved items as implicit assumptions — leave them in `questions_generated` for the human grill gate.
