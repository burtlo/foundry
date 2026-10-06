# `visit present complete`

Status: **implemented**

Publish presentation and transition after accepted presentation judgment.

## Invocation

```bash
foundry visit present complete [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--visit` | no | — | Visit id (default: active visit) |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--summary` | no | — | Short summary for visit transition on success |
| `--revision` | no | — | Expected snapshot revision before commit |
