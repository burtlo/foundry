---
name: orchestrate-build
description: >-
  Run plan-bundle implementation as an orchestrator: one package at a time via
  plan-implementer and independent plan-verifier subagents. Use after
  /spec-implementation-map with a bundle directory or implementation.md path.
---

# Orchestrate build

Follow [the orchestrate-build skill](../skills/orchestrate-build/SKILL.md).

**Role:** orchestrator only — delegate implementation and verification; do not edit product code yourself.

## User input

| Field | Source |
|-------|--------|
| `bundle_dir` | **Either** `@`-mentioned directory under `docs/plans/<bundle>/` |
| `implementation_path` | **Or** `@`-mentioned `implementation.md` (parent directory = bundle) |
| `packages` | Optional — comma-separated package IDs (`P1`, `P4`) |
| `from_package` | Optional — resume at package ID |
| `auto_continue` | Optional — advance through packages without per-package user gate |
| `repair_limit` | Optional — verifier fail retries (default 1) |

If the user invokes **`/orchestrate-build`** with only `@docs/plans/<bundle>/` or `@.../implementation.md`, treat that as the path input.

## Procedure

1. Load the skill contract; resolve bundle and read `implementation.md` + `spec.md`.
2. Validate orchestration packages and briefs exist; otherwise stop and recommend `/spec-implementation-map`.
3. Present the **agenda** (queue, dependencies, gates) and **stop** unless the user already said to start or passed a single-package `packages` filter with explicit run intent.
4. For each package in order: Task **plan-implementer** → Task **plan-verifier** (separate, fresh) → optional repair loop → update `orchestration-progress.md` → gate before next package unless `auto_continue`.
5. Close with a run summary; do not commit unless requested.
