# Phase 5 — User CLI for Shape

## Purpose

Let developers initialize a repository and shape a request without knowing visits, receipts, or node IDs.

## Delivery steps

1. Implement foundry init around app discovery, manifest setup, and config validation, with preview before writing.
2. Implement shape, runs, status, and attach; persist the exact work request before advancing.
3. Implement answer, decide, retry, cancel, and host status/start/stop with explicit IDs and typed errors.
4. Render position, questions, choices, failures, and next actions. Attach shows a snapshot, then event stream; Ctrl-C detaches.
5. Add versioned --json envelopes and documented exit codes. Move low-level controls into a developer/internal namespace after compatibility.
6. Run a clean-repository usability pass and revise command names/messages based on observed friction.

## Expected deliverables

User CLI, help/examples, JSON and exit-code contract, compatibility/deprecation map, end-to-end Shape tests, usability notes.

## Acceptance criteria

- A developer initializes and starts Shape without manually editing Foundry files.
- Both no-question and question/answer paths reach plan presentation.
- Shape gates require a recorded user decision; Execute never starts silently.
- Status shows where a run is, what it needs, and why it stopped; attach reconnects.
- Ctrl-C detaches; cancel records a distinct action.
- JSON output is parseable; diagnostics use stderr; exit codes distinguish usage, validation, conflict, unavailable host, and run failure.
- Completing Shape requires no direct visit transition, receipt seal, or artifact publish command.

**Handoff:** Phase 6 expands the same contracts to Execute and Verify.
