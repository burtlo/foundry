The Foundry workflow has been implemented through Shape → Execute → Verify, but a repository review discovered that several worker agents referenced by the workflow do not have prompt files.

Existing:

- `shape-presenter.md`
- `shape-recorder.md`

Missing:

- `intake-checker.execute.md`
- `planner.md`
- `repairer.md`
- `commit-agent.md`
- `intake-checker.verify.md`
- `implementation-validator.md`

This is an implementation-completeness issue, not merely a documentation issue.

Your task is to reconstruct, implement, and verify the missing worker-agent prompt contracts.

## Important constraint

Do NOT invent the responsibilities of these agents from their filenames.

Derive each worker's contract from the existing Foundry implementation.

The orchestration code, state model, feature documents, tests, phase instructions, and call sites are authoritative evidence for what each worker is expected to do.

If those sources disagree, report the disagreement rather than silently choosing one interpretation.

## Phase 1 — Discover every worker

First, inspect the entire Shape → Execute → Verify lifecycle.

Find every place where Foundry:

- invokes a worker agent
- names a worker role
- expects structured output from a worker
- consumes an artifact produced by a worker
- branches based on a worker result

Build a complete worker inventory.

Do not assume the supplied missing-file list is exhaustive.

For every worker record:

**Worker**
**Phase**
**Prompt file**
**Invoked by**
**Inputs**
**Expected work**
**Expected output**
**Output consumer**
**Failure behavior**

Compare this inventory against the prompt files that actually exist.

## Phase 2 — Reconstruct the missing contracts

For each missing prompt, trace its invocation from beginning to end.

Determine:

1. Why is this worker invoked?
2. What information does Foundry provide to it?
3. What decisions belong to this worker?
4. What decisions must NOT belong to this worker?
5. What artifacts/state can it read?
6. What artifacts is it expected to produce?
7. What output format does the caller expect?
8. What constitutes success?
9. What constitutes failure?
10. What should happen when information is insufficient?
11. What state transition, if any, depends on its result?

Pay special attention to the architectural boundary:

**Foundry controls workflow and deterministic state transitions. Workers perform bounded judgment/work.**

Do not give a worker responsibility for advancing the workflow if Foundry itself owns that transition.

## Phase 3 — Implement the prompts

Create the missing prompt files:

### `intake-checker.execute.md`

Determine what Execute requires from intake before execution may proceed.

It should evaluate the required intake contract, not generally re-investigate the project unless the implementation explicitly requires that.

### `planner.md`

Determine the exact planning responsibility expected during Execute.

Clearly distinguish planning from Shape. Do not accidentally recreate Shape inside Execute.

The planner should produce exactly the implementation-planning artifact the execution workflow consumes.

### `repairer.md`

Determine when repair is invoked, what failed state/evidence it receives, what it is allowed to change, and what must be true before control returns to Foundry.

Repair must be bounded by the failure it is attempting to correct.

### `commit-agent.md`

Reconstruct this contract from the actual commit-agent invocation, including the example/reference around the previously identified line ~624 if it remains relevant.

Determine:

- what may be committed
- required preconditions
- how the commit message is determined
- whether unrelated changes must be excluded
- what result is returned to Foundry
- what happens if there is nothing valid to commit

Do not give this worker broader source-control authority than its caller expects.

### `intake-checker.verify.md`

Determine what Verify requires before verification begins.

Do not assume this is identical to `intake-checker.execute.md`.

If Execute and Verify have different intake requirements, encode those differences explicitly.

If substantial behavior is shared, preserve a clear common conceptual contract without obscuring phase-specific requirements.

### `implementation-validator.md`

Determine what constitutes implementation validation.

Trace exactly what evidence Verify supplies and what it expects back.

The validator should determine whether the implementation satisfies the shaped requirements/acceptance criteria—not merely whether tests ran successfully.

Clearly distinguish:

- validation passed
- implementation does not satisfy requirements
- validation could not be completed
- infrastructure/tooling failure

where supported by the existing workflow.

## Phase 4 — Check prompt consistency

Compare all worker prompts, including the existing:

- `shape-presenter.md`
- `shape-recorder.md`

Look for consistency in:

- role definition
- input handling
- output contracts
- authority boundaries
- failure reporting
- state mutation
- terminology
- interaction with Foundry

Do not rewrite the existing prompts merely for stylistic consistency. Change them only if you discover an actual contract mismatch.

## Phase 5 — Add contract coverage

The system should make it difficult to repeat this failure.

Add or strengthen tests/checks so that a workflow cannot reference a worker prompt that does not exist.

At minimum, investigate whether Foundry can deterministically verify:

**Every worker-agent reference in the workflow resolves to an existing prompt.**

Prefer a general invariant over six tests hardcoded to these particular filenames.

If the architecture supports it, also validate that required prompt resources are loadable during startup/configuration rather than discovering missing prompts halfway through a run.

## Phase 6 — End-to-end verification

After implementing the prompts, trace the lifecycle again:

Shape
→ Execute
→ Verify

For every worker invocation verify:

**caller → prompt exists → inputs available → worker contract → output produced → output consumed → deterministic transition**

Look specifically for additional workers that exist conceptually but still lack implementation.

Run the relevant test suite and feature/documentation validation.

## Deliverable

Implement the missing worker prompts and appropriate contract checks.

Then report:

### Worker inventory
Every worker discovered across Shape → Execute → Verify and its prompt file.

### Prompts created
For each new prompt, summarize the contract you reconstructed and the evidence used to derive it.

### Contract inconsistencies
Anything where orchestration, features, tests, and prompt expectations disagree.

### Guardrail added
Explain how the repository will now detect a workflow referencing a nonexistent worker prompt.

### Verification
Show how you established that every worker invocation from Shape through Verify now resolves to an implemented worker contract.

### Remaining gaps
Identify anything that prevents you from confidently stating:

> Every worker required by the implemented Shape → Execute → Verify lifecycle has an explicit, usable prompt contract.