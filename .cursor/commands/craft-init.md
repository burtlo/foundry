---
name: craft-init
description: >-
  Bootstraps a Foundry application repository by discovering mechanics and
  writing a validated .foundry/app.yaml manifest. Use when the repo lacks a
  manifest, manifest validation fails, or the user asks to initialize Foundry.
---

# Craft init

Role: bootstrap steward — discover application mechanics and commit `.foundry/app.yaml`.

## User input

Capture the user's **bootstrap intent** verbatim (for example: onboard this repo, repair a missing manifest, or re-run discovery after repo changes). Do not infer commands from AGENTS.md, solution files, or Makefiles without running discovery.

## Bootstrap

```foundry-invoke
cli resolve --json
```

```foundry-invoke
app discover --json
```

Present the proposed manifest, unresolved questions, and any `ignore_issues`. Stop if `ignore_issues` is non-empty and tell the human to replace broad `.foundry` ignore rules with `.foundry/runs/`.

After human confirmation, write a temporary manifest input file outside `{workspace}/.foundry` and preview:

```foundry-invoke
app init --manifest-file "{manifest_input}" --dry-run --json
```

On validation failure, stop and report errors. Never add `--force` unless the human explicitly approves replacing a different existing manifest.

```foundry-invoke
app init --manifest-file "{manifest_input}" --json
```

```foundry-invoke
app validate --json
```

Report the validated manifest id and path for commit. Delete the temporary manifest input after init.

## Out of scope

| Command | Use when |
|---|---|
| `/craft-shape` | Start a shape-phase run (requires a valid manifest) |
| `/craft-execute` | Execute phase (new chat after shape completes) |
| `/craft-resume` | Continue an existing run in a fresh chat |
| `/craft-status` | Inspect run position without starting or advancing work |
