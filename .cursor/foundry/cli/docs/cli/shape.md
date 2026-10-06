# `shape`

Status: **implemented**

Create a run from a shape request and advance into Shape (Phase 5 user CLI).

## Invocation

```bash
foundry shape [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--input` | no | — | Verbatim shape request text |
| `--input-file` | no | — | Path to a file containing the shape request |
| `--flow` | no | — | Flow id (default: implementation) |
| `--run-id` | no | — | Explicit run id slug |
| `--no-host` | no | false | Do not auto-start the job host; advance on disk when host is not running |
| `--local` | no | false | Use disk/engine directly even when the job host is running |
