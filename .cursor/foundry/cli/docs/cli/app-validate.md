# `app validate`

Status: **implemented**

Validate `.foundry/app.yaml` against `app-manifest.schema.json`. Read-only probe used by the `validate-manifest` catalog check.

## Invocation

```bash
foundry app validate [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--manifest` | no | — | Explicit manifest path (default: workspace .foundry/app.yaml) |
