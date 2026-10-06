# `artifact publish`

Status: **implemented**

Validate and publish a declared artifact for the active visit.

## Invocation

```bash
foundry artifact publish [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--visit` | no | — | Visit id (default: active visit) |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--artifact` | yes | — | Logical artifact id |
| `--source` | yes | — | Source run: or workspace: path |
| `--revision` | no | — | Expected snapshot revision before commit |
