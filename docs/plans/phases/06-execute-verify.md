# Phase 6 — Execute and Verify

## Purpose

Extend the proven engine/host/CLI path to implementation and verification. Execution begins only after an explicit developer action.

## Delivery steps

1. Classify each Execute/Verify node as deterministic operation, agent task, user gate, or hybrid; migrate one node at a time.
2. Implement foundry start RUN at the existing Execute start gate, valid only after Shape is recorded.
3. Add bounded command operations with declared working directory, arguments, timeout, output capture, and write scope.
4. Migrate planning/build/repair judgment to strict task results; keep branch, commit, test, and evidence mechanics in engine operations when appropriate.
5. Preserve verification checks, human gates, repair/replan/reshape routes, and ledger-based loop limits.
6. Show command progress, verification results, artifacts, blocked reasons, and decisions in attach/status.

## Expected deliverables

Migrated node declarations, operations, task contracts, start command, user docs, end-to-end and restart tests, responsibility map.

## Acceptance criteria

- Execute cannot start without a valid explicit start action recorded with actor and revision.
- Deterministic branch/command/artifact/receipt/transition work is host-owned and idempotent.
- Failed verification follows declared policy and exposes result and next action.
- Repair and reverify limits survive restart and use ledger history.
- Agent outputs cannot choose routes or bypass gates; human decisions are attributed and validated.
- A developer starts, observes, interacts with, and completes Execute and Verify using user commands, with durable evidence for every visit.

**Handoff:** Consider TUI or web UI only after the host protocol and CLI are stable.
