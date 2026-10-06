# `host stop`

Status: **implemented**

Stop the background job host.

## Invocation

```bash
foundry host stop [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--idempotency-key` | no | — | Client idempotency key for host.stop |
