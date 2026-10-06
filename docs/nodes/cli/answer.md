# `answer`

Status: **implemented**

Submit clarifying answers when wait.kind is user_input.

## Invocation

```bash
foundry answer [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `run` | yes | — | Run id |
| `--answers` | yes | — | JSON object mapping question id to answer text, e.g. '{"q1": "Use REST"}' |
| `--revision` | no | — | Expected snapshot revision; returns STALE_REVISION on conflict |
| `--local` | no | false | Answer on disk even when the job host is running |
