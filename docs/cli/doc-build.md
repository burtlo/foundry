# `doc build`

Status: **implemented**

Generate flow, node, and CLI documentation under the Foundry repository `docs/` directory (default: `{repo_root}/docs` from the resolved registry bundle). Do not use `docs/nodes` as `--output` — that creates duplicate nested trees. Worker catalog pages are emitted only when flow nodes declare a `worker:` binding.

## Invocation

```bash
foundry doc build [flags]
```

Global flags (`--workspace`, `--registry`, `--json`) are documented in [cli/index.md](index.md).

## Command flags

| Flag | Required | Default | Description |
|---|:---:|:---:|---|
| `--flow` | no | implementation | Flow id (default: implementation) |
| `--node` | no | — | Generate documentation for a single node only |
| `--output` | no | — | Output directory (default: docs) |

## Acceptance

[doc_build.feature](../../.cursor/foundry/cli/tests/acceptance/features/doc_build.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
