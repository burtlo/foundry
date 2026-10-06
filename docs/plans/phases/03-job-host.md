# Phase 3 — Persistent local job host

## Purpose

Run the engine independently of CLI lifetime. The first host is local and owns one workspace.

## Delivery steps

1. Define a versioned JSON protocol over a workspace Unix socket: request ID, expected revision, mutation idempotency key, typed errors.
2. Implement start/discovery, one-owner locking, owner-only socket permissions, health, stop, and restart reconciliation.
3. Expose run.create/get/list/events/advance/answer/decide/retry/cancel.
4. Stream events by sequence cursor and support reconnection.
5. Dispatch committed outbox work with bounded concurrency and reviewable failures.

## Expected deliverables

Host executable, client library, protocol and error catalog, startup/recovery guide, separate-process integration tests.

## Acceptance criteria

- The CLI can exit while the host continues a run.
- Host restart restores nonterminal runs and pending waits or tasks.
- A second host cannot own the same workspace.
- Racing clients cannot both commit against the same revision.
- Event reconnection from after_seq misses no events and presents no duplicate events.
- Terminal disconnect or Ctrl-C does not cancel a run.
- Host unavailability yields a typed error without corrupting state.

**Handoff:** Phase 4 adds a model adapter behind the agent boundary.
