# `run list`

Status: **implemented**

List workspace runs.

## Invocation

```bash
foundry run list [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--local` | no | false | Read runs from disk even when the job host is running |
