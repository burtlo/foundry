# Phase 4 — Model API connection

## Purpose

Run declared judgment tasks through direct model API calls. Workflow declarations specify task input/output; host configuration chooses the provider/model.

## Delivery steps

1. Define immutable request/result envelopes, strict task schemas, prompt/input digests, input selection, and context limits.
2. Implement a provider-neutral adapter and one direct model API adapter; keep credentials in host configuration.
3. Persist request/outbox before dispatch, retain raw response, validate output, and accept only a matching active wait/attempt.
4. Add bounded transport/schema retries, timeout, and restart reconciliation for uncertain dispatch.
5. Generate receipts and provenance in the host, never in the model response.
6. Prove Examination's question/answer loop with prior answers in the next request.

## Expected deliverables

Adapter interface, one API adapter, fake adapter for tests, versioned schemas, receipt migration, model configuration, integration tests.

## Acceptance criteria

- Examination gets only declared bounded context and judgment instructions; no Foundry CLI or unrestricted file writes.
- A valid result updates Examination through the engine.
- Questions have stable IDs; human answers are attributed and used on resume.
- Malformed output retries within policy; exhaustion retains a reviewable error and raw response reference.
- Late, duplicate, or wrong-visit results cannot mutate a run.
- Restart after uncertain dispatch accepts at most one result per attempt.
- Secrets appear in no request, run file, receipt, or normal log.

**Handoff:** Phase 5 exposes Shape through user commands.
