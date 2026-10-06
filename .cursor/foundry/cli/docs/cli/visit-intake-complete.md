# `visit intake complete`

Status: **implemented**

Complete shape intake with work prompt (engine hook).

## Invocation

```bash
foundry visit intake complete [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--visit` | no | — | Visit id (default: active visit) |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--work-prompt` | no | — | Verbatim work request; omit to record blocked intake without transition |
| `--source-type` | no | chat | How the work request was supplied |
| `--source-ref` | no | — | Optional file path or URL reference |
| `--summary` | no | — | Short summary for visit transition on success |
| `--revision` | no | — | Expected snapshot revision before commit |
