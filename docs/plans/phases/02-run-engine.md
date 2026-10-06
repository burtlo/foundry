# Phase 2 — Durable advancement and recovery

## Purpose

Make the existing run a resumable job and a visit a node occurrence. The engine alone moves between visits.

## Delivery steps

1. Implement bounded advance(run_id) around hooks, operations, waits, close/seal, and routing.
2. Add durable waits for agent, user input, decision, and operator intervention. Keep wait kind separate from run status.
3. Add result/input submission requiring matching run, visit, wait ID, and expected revision.
4. Make ledger/state updates transactional or replayable. Add per-run locking, operation IDs, revision checks, and a durable side-effect outbox.
5. Pin each run to a registry digest and explicitly migrate old snapshot.json runs.
6. Expose structured inspection of position, status, wait, reason, failures, and history cursor.

## Expected deliverables

Advance and submission APIs; versioned run/wait/event contracts; recovery procedure and migration; workflow and crash-boundary tests.

## Acceptance criteria

- Valid Intake reaches Examination and stops with an inspectable agent request.
- Failed Intake stays put with a structured reason and no agent request.
- A valid result attaches to the correct visit and cannot be accepted twice.
- Repeating advance does not duplicate artifacts, receipts, seals, or connections.
- A fresh process recovers after event commit but before snapshot refresh.
- Stale concurrent mutation fails with a revision conflict.
- Routing ambiguity yields definition_error; operation failure yields execution_error; check failure follows policy.
- No connection is taken before the source visit seals.

**Handoff:** Phase 3 exposes this engine through a persistent host.
