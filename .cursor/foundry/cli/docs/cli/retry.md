# `retry`

Status: **implemented**

Retry a halted, execution_error, paused, or operator-wait run.

## Invocation

```bash
foundry retry [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `run` | yes | — | Run id |
| `--reason` | no | — | Optional reason recorded in the ledger |
| `--revision` | no | — | Expected snapshot revision |
| `--local` | no | false | Retry on disk even when the job host is running |
