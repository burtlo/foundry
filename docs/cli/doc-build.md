# `doc build`

Status: **implemented**

Generate flow, node, worker, and CLI documentation under the docs directory from factory-flow.yaml, registry artifacts, and this CLI's command surface.

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
| `--all-nodes` | no | false | Generate documentation for every node (default when --node is omitted) |
| `--output` | no | — | Output directory (default: docs) |

## Acceptance

[doc_build.feature](../../.cursor/foundry/cli/tests/acceptance/features/doc_build.feature)

## Implementation

[.cursor/foundry/cli/foundry.py](../../.cursor/foundry/cli/foundry.py)
