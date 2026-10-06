# `dev all`

Status: **implemented**

Run unit tests then acceptance tests.

## Invocation

```bash
foundry dev all [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--quiet` | no | false | Reduce pytest verbosity |
| `--include-dev-scenarios` | no | false | Also run dev_commands.feature in the acceptance leg |
| `pytest_args` | no | — | Extra arguments passed to pytest |
