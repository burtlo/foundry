# `config init`

Status: **implemented**

Write `.foundry/foundry.yaml` with a registry pointer to the Foundry bundle. Defaults to probing `../foundry/.cursor/foundry` from the workspace.

## Invocation

```bash
foundry config init [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--registry` | no | — | Registry path relative to workspace (default: probe ../foundry/.cursor/foundry) |
| `--flow` | no | — | Default flow id (default: implementation) |
| `--dry-run` | no | false | Validate and preview without writing |
| `--force` | no | false | Overwrite an existing foundry.yaml |
