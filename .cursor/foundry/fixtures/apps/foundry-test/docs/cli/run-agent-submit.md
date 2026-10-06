# `run agent submit`

Status: **implemented**

Submit a validated agent result for the active agent wait.

## Invocation

```bash
foundry run agent submit [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--run` | no | — | Run id |
| `--run-dir` | no | — | Run directory containing snapshot.json |
| `--request-id` | yes | — | Agent request id (ar_…) |
| `--result-json` | no | — | Inline JSON result object |
| `--result-file` | no | — | Path to JSON result file |
| `--revision` | no | — | Expected snapshot revision; returns STALE_REVISION on conflict |
| `--local` | no | false | Submit on disk even when the job host is running |
