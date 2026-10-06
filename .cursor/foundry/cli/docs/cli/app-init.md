# `app init`

Status: **implemented**

Write `.foundry/app.yaml` from a validated manifest input file. Hard block on validation failure unless `--dry-run`.

## Invocation

```bash
foundry app init [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--manifest-file` | yes | — | Path to manifest YAML or JSON input |
| `--dry-run` | no | false | Validate and preview without writing |
| `--force` | no | false | Overwrite an existing manifest |
