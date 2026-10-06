---
name: craft-shape
description: >-
  Starts a new shape-phase run for the implementation flow: admits shape.intake,
  completes engine-owned intake, then loads steward context at shape.examine. Use when
  the user wants to shape a feature, capture a work request, or begin the Foundry shape chat.
---

# Craft shape

Role: shape-phase steward — bootstrap a run and hand off to the active visit step.

Follow [steward UX](../rules/steward-ux.mdc): lead each turn with a plain-language intent sentence; use `foundry-invoke` fences only; at user gates, presentation turn then decision turn.

## User input

Capture the user's **work request** as `work_prompt` verbatim. Do not interpret, expand, or fetch content. `work_prompt` is captured in chat only — retain it verbatim through `shape.intake`; it is not persisted in the context packet after reload.

## Bootstrap

Run from the application workspace. Derive provisional `$cli_path` from `.foundry/foundry.yaml` (`{registry}/cli/foundry.sh`) when present; then:

```foundry-invoke
cli resolve
```

Cache the returned `cli_path` from the resolve response; use `$cli_path --json <argv>` for all Shell invocations (see [steward UX](../rules/steward-ux.mdc)).

On `REGISTRY_NOT_FOUND`, direct the user to run `config init` (or add `.foundry/foundry.yaml`) and stop.

```foundry-invoke
run create --flow implementation --json
```

On failure (manifest missing or invalid), direct the user to `/craft-init` and stop.

Persist `work_prompt` in chat until intake completes:

```foundry-invoke
visit intake complete --run "{run_id}" --work-prompt "<verbatim work request>"
```

Alternatively, set `config.shape.work_prompt` on `run create` and use `run advance` to let the host complete intake.

Optional: when the application repo root differs from the workspace, patch `app_folder` before complete:

```foundry-invoke
visit state patch --run "{run_id}" --set '{"app_folder": "<path>"}'
```

`shape.intake` has no step judgment file — the context packet at intake describes engine-owned completion only. After intake passes, load instructions for the active visit:

```foundry-invoke
run context --run "{run_id}" --markdown
```

Follow the markdown packet — judgment for `shape.examine` is inlined under `## Judgment`.

At **shape.examine**: run the `shape.examine` agent task, submit the structured result with `run agent submit`, answer clarifying questions with `answer` when the wait is `user_input`, then complete with `visit examine complete` (or `run advance` when no open questions remain). Use `visit examine complete --with-open-questions` only to proceed to the examination gate without answering. Do not manually seal agent receipts or call `visit transition` on this node.

At **shape.present**: run the `shape.present` task, submit with `run agent submit`, then complete with `visit present complete` (or `run advance` after a PROCEED verdict). A BLOCKED verdict seals the agent receipt only — resolve blockers and submit again before completing. Do not manually publish artifacts, seal receipts, or call `visit transition` on this node.

At **shape.examine.gate**, use the two-turn gate pattern: present examination state from the packet (`reads.state`, inlined `## Instructions`), then `gate decide` on the next user message — same UX contract as **shape.present.gate**.

After `visit examine complete`, `visit transition` (on nodes that allow it), or `gate decide` succeeds, re-run `run context --markdown` before following the next visit's instructions.

## Out of scope

| Command | Use when |
|---|---|
| `/craft-init` | Application repo needs `.foundry/app.yaml` bootstrap |
| `/craft-execute` | Execute phase (requires a new chat after shape completes) |
| `/craft-resume` | Continue an existing run in a fresh chat |
| `/craft-status` | Inspect run position without starting or advancing work |
