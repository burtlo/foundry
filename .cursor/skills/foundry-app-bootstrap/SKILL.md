---
name: foundry-app-bootstrap
description: >-
  Discovers and creates a validated .foundry/app.yaml for an application
  repository. Use when onboarding an app to Foundry, repairing a missing app
  manifest, or invoking /craft-init.
---

# Foundry app bootstrap

Create `.foundry/app.yaml` through the Foundry CLI. The CLI owns schema validation and YAML output; do not hand-write the manifest.

## Discover

```foundry-invoke
app discover --json
```

Present command candidates from `proposed_manifest` and `unresolved_questions`. Ask the human to confirm:

- stable lower-kebab application `id` and descriptive `tags`;
- command `argv`, `cwd`, timeout, and platform variants;
- ordered `verification.implementation` and `verification.post_repair`;
- default builder and routing globs (`general-builder` in v1).

Do not turn unresolved detector output into guessed commands.
If discovery reports `ignore_issues`, stop before init and tell the human to replace the broad rule with `.foundry/runs/`.

v1 manifests must not include a `documentation` section.

## Initialize

Create a temporary YAML input document outside `{workspace}/.foundry`. Its root is the confirmed manifest object (`schema_version: 1`, `id`, `commands`, `verification`, `builders`, and optional `tags`).

Preview without writing:

```foundry-invoke
app init --manifest-file "{manifest_input}" --dry-run --json
```

After the human confirms the preview, run the same command without `--dry-run`. Never add `--force` unless the human explicitly approves replacing a different existing manifest. Repeating init with identical input is safe and reports no change.

Delete the temporary input after init.

## Registry pointer

If `.foundry/foundry.yaml` is missing, create it before shape-phase commands:

```foundry-invoke
config init --json
```

```foundry-invoke
config validate --json
```

Do not symlink `.cursor/foundry` into application repos; commit `foundry.yaml` with a relative `registry` path instead.

## Validate and verify Git visibility

```foundry-invoke
app validate --json
```

From the workspace, run:

```bash
git check-ignore -v --no-index .foundry/app.yaml
```

Exit `1` with no matching rule means the manifest is not ignored. If a rule such as `.foundry/` ignores it, stop and tell the human to replace that broad rule with `.foundry/runs/`; do not silently edit unrelated ignore entries.

Then run:

```bash
git status --short -- .foundry/app.yaml
```

Report the validated manifest id and `.foundry/app.yaml` for commit.
