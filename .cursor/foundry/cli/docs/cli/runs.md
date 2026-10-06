# `runs`

Status: **implemented**

List workspace runs with status, active node, and wait kind.

## Invocation

```bash
foundry runs [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--local` | no | false | Read from disk even when the job host is running |
