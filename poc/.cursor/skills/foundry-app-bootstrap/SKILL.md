---
name: foundry-app-bootstrap
description: >-
  Discovers and creates a validated .foundry/app.yaml for an application
  repository. Use when onboarding an app to Foundry, repairing a missing app
  manifest, or invoking /foundry-app-bootstrap.
---

# Foundry app bootstrap

Create `.foundry/app.yaml` through the deterministic Foundry CLI. The CLI owns
schema validation and YAML output; do not hand-write the manifest.

## Resolve paths

- `{app_folder}` is the application repository selected by the user. If the
  workspace has multiple app repositories and none was named, ask which one.
- `{factory_root}` is the bundle containing this skill and
  `.cursor/foundry/cli/foundry.py`.

## Discover

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" app discover --app-folder "{app_folder}"
```

Present command candidates with their evidence. Ask the human to confirm:

- stable lower-kebab application `id` and descriptive `tags`;
- command `argv`, `cwd`, timeout, and platform variants;
- ordered `verification.implementation` and `verification.post_repair`;
- default builder and every route owner, priority, and glob;
- documentation model and model configuration;
- intended validation mode: `implementation` or `analysis`.

Do not turn unresolved detector output into guessed commands.
If discovery reports `ignore_issues`, stop before init and tell the human to
replace the broad rule with `.foundry/runs/`.

## Initialize

Create a temporary JSON input document outside `{app_folder}/.foundry`. Its
root is the confirmed manifest object (`schema_version: 1`, `id`, `commands`,
`verification`, `builders`, `documentation`, and optional `tags`). This is CLI
input, not the authored YAML.

Preview without writing:

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" app init --app-folder "{app_folder}" --manifest-file "{temporary_manifest_input}" --run-mode "{run_mode}" --dry-run
```

After the human confirms the preview, run the same command without
`--dry-run`. Never add `--force` unless the human explicitly approves replacing
a different existing manifest. Repeating init with identical input is safe and
reports no change.

Delete the temporary input after init.

## Validate and verify Git visibility

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" app validate --app-folder "{app_folder}" --run-mode "{run_mode}"
```

From `{app_folder}`, run:

```text
git check-ignore -v --no-index .foundry/app.yaml
```

Exit `1` with no matching rule means the manifest is not ignored. If a rule
such as `.foundry/` ignores it, stop and tell the human to replace that broad
rule with `.foundry/runs/`; do not silently edit unrelated ignore entries.

Then run:

```text
git status --short -- .foundry/app.yaml
```

Report the validated manifest ID/hash and `.foundry/app.yaml` for commit.
