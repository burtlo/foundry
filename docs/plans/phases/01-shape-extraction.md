# Phase 1 — Extract deterministic Shape work

## Purpose

Demonstrate the judgment/mechanism boundary without building the host. Retain the run/visit model and compatibility entry points.

## Delivery steps

1. Persist the exact original work request and source reference at run creation.
2. Add engine-owned Intake operations for input/config validation, raw ticket creation, artifact publication, evidence, and close request. Checks observe; operations mutate.
3. Migrate the ticket contract so normalized_translation is optional at Intake or produced later by Examination.
4. Keep a declared Intake agent task only for genuine semantic judgment that cannot yet be made deterministic.
5. Define Examination's structured semantic result: summary, draft acceptance criteria, assumptions, decisions, and questions.
6. Remove state patching, receipt assembly, publication, routing, and CLI presentation instructions from agent Markdown.

## Expected deliverables

Refactored Intake and Examination declarations and prompts; minimal operation/task result contracts; ticket schema migration; before/after responsibility table; focused tests and docs.

## Acceptance criteria

- Valid Intake publishes a raw ticket, seals once, and reaches Examination without a model call.
- Missing request or invalid configuration yields a structured check/policy reason, no ticket, and no transition.
- A new process can read the original request byte-for-byte.
- Examination receives declared context and returns a schema-validated result; questions are represented structurally for Phase 2 to turn into a durable user-input wait.
- Agent-facing instructions contain no Foundry CLI, known-state checks, receipts, artifact publication, transitions, or presentation formatting.
- Intentional changes to Shape acceptance behavior are documented.

**Handoff:** Phase 2 wraps these operations in central advancement.
