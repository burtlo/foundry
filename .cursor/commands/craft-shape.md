---
name: craft-shape
description: >-
  Starts a new shape-phase run for the implementation flow: admits shape.intake,
  loads steward context, and defers to step instructions. Use when the user wants
  to shape a feature, capture a work request, or begin the Foundry shape chat.
---

# Craft shape

Role: shape-phase steward — bootstrap a run and hand off to the active visit step.

Follow [steward UX](../rules/steward-ux.mdc): lead each turn with a plain-language intent sentence; use `foundry-invoke` fences only; at user gates, presentation turn then decision turn.

## User input

Capture the user's **work request** as `work_prompt` verbatim. Do not interpret, expand, or fetch content. `work_prompt` is captured in chat only — retain it verbatim through `shape.intake`; it is not persisted in the context packet after reload.

## Bootstrap

```foundry-invoke
cli resolve --json
```

On `REGISTRY_NOT_FOUND`, direct the user to run `config init` (or add `.foundry/foundry.yaml`) and stop.

```foundry-invoke
run create --flow implementation --json
```

On failure (manifest missing or invalid), direct the user to `/craft-init` and stop.

```foundry-invoke
run context --run "{run_id}" --markdown
```

Follow the markdown packet — step instructions are inlined under `## Instructions`. Pass `work_prompt` into the step when it instructs you to launch the worker.

After `visit transition` or `gate decide` succeeds, re-run `run context --markdown` before following the next visit's inlined instructions.

## Out of scope

| Command | Use when |
|---|---|
| `/craft-init` | Application repo needs `.foundry/app.yaml` bootstrap |
| `/craft-execute` | Execute phase (requires a new chat after shape completes) |
| `/craft-resume` | Continue an existing run in a fresh chat |
| `/craft-status` | Inspect run position without starting or advancing work |
