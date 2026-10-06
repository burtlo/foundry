# `receipt seal`

Status: **implemented**

Validate a receipt draft, fill provenance, and append receipt.linked (capability receipt.link).

## Invocation

```bash
foundry receipt seal [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--visit` | no | — | Visit id (default: active visit) |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--schema` | no | — | Receipt schema registry path |
| `--file` | yes | — | run: or workspace: path to receipt JSON draft |
| `--revision` | no | — | Expected snapshot revision before commit |
