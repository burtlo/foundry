# Foundry: Extract Deterministic Node Instructions

> **Workflow gap closure (Shape → Execute → Verify):** use [orchestrator-brief.md](orchestrator-brief.md) and [shape-execute-verify-gap-closure-plan.md](shape-execute-verify-gap-closure-plan.md). This file is the plan for **deterministic vs judgment extraction** in Shape nodes.

## Objective

Refactor the existing Shape workflow node definitions so that deterministic workflow behavior is separated from agent judgment.

Today, node Markdown instructions mix several responsibilities:

- deterministic operations
- workflow policy
- checks and gates
- presentation/output formatting
- agent reasoning and judgment

The goal of this work is to identify and extract everything that does **not** require an LLM/agent, leaving behind a much smaller set of Markdown instructions representing only the work that genuinely requires agent judgment.

This is a refactoring and architectural discovery task.

Do **not** build the future job runner, background service, TUI, or redesigned CLI as part of this work.

## Starting Scope

Start with the existing **Shape** phase.

Pay particular attention to:

1. Shape Intake
2. Shape Examination
3. The transition between Intake and Examination

These should serve as the first concrete examples from which we can discover the reusable deterministic operations required by Foundry.

Inspect surrounding Shape nodes when necessary to determine whether an instruction represents a repeated pattern, but do not attempt to redesign the entire workflow at once.

## Classification Model

For every instruction currently contained in the node definitions/Markdown, classify it into one of four categories.

### 1. Judgment

Requires interpretation, reasoning, synthesis, or another capability for which an agent is appropriate.

Examples:

- Determine whether the user's request is sufficiently understood.
- Examine the request and project context.
- Identify ambiguity.
- Generate useful clarification questions.
- Incorporate the user's answers.
- Produce or refine an artifact based on contextual understanding.

These instructions should generally remain in agent-facing Markdown.

### 2. Mechanism

A deterministic operation the Foundry runtime can perform.

Examples:

- Read a file.
- Determine whether a file exists.
- Run a command.
- Inspect the current Git branch.
- Write a receipt.
- Persist a result.
- Move to another node.
- Invoke an agent.
- Record the result of an agent invocation.

These should not require an agent.

### 3. Policy

Rules controlling whether execution is allowed to proceed or what transition should occur.

Examples:

- Required configuration must exist before entering a node.
- A failed check blocks execution.
- All required checks must pass before advancing.
- A gate must be approved before continuing.
- A particular artifact must exist before leaving a node.

These belong in executable workflow/node configuration or engine behavior rather than prose instructions given to an agent.

### 4. Presentation

Instructions describing how information should be shown to the user.

Examples:

- Print a header.
- Print a footer.
- Display the current phase/node.
- Format errors.
- Tell the user which check failed.
- Display completion information.

These belong to the CLI/UI presentation layer rather than agent instructions.

## Important Principle

Do not use an agent to interpret state that Foundry already knows deterministically.

For example, an instruction equivalent to:

> Check whether any of the checks failed before continuing.

should not exist as an agent instruction.

If Foundry executes a check, Foundry already knows whether that check succeeded.

The runtime should enforce:

    check failed
        ↓
    node cannot proceed

The agent should never be asked to rediscover or interpret this condition.

Apply this principle throughout the examined nodes.

## Phase 1 — Inventory Existing Instructions

Inspect the Shape node definitions and supporting Markdown.

For each instruction, document:

- where it currently lives
- what it currently asks the agent/system to do
- its classification:
  - Judgment
  - Mechanism
  - Policy
  - Presentation
- whether it should remain agent-facing
- where it should eventually live if extracted

Do not immediately rewrite everything.

First create an inventory so that we can see what responsibilities are currently mixed together.

## Phase 2 — Identify Repeated Deterministic Concepts

Look across the Shape nodes for repeated deterministic behaviors.

Examples may include:

- executing checks
- evaluating check results
- blocking on failure
- recording failures
- writing receipts
- determining node completion
- transitioning to the next node
- invoking a subagent
- collecting an agent result
- presenting headers/footers
- displaying status
- waiting for user input

Do not assume this list is complete.

Derive the actual primitives from the repository.

Where multiple Markdown instructions describe essentially the same deterministic operation, identify that as a candidate reusable Foundry primitive.

## Phase 3 — Define the Boundary

For Intake and Examination, describe what execution should look like after responsibilities are separated.

For example, Intake may ultimately resemble:

    enter intake
        ↓
    engine executes admission checks
        ↓
    failure → stop/block and persist reason
        ↓
    success
        ↓
    perform any required deterministic operations
        ↓
    evaluate completion
        ↓
    transition to examination

There may be little or no agent judgment required in Intake.

Examination may instead resemble:

    enter examination
        ↓
    engine performs deterministic checks/setup
        ↓
    engine constructs agent context
        ↓
    invoke agent with judgment-only instructions
        ↓
    agent examines request/context
        ↓
    agent may request clarification
        ↓
    result returned to engine
        ↓
    engine persists result/evidence
        ↓
    completion policy evaluated
        ↓
    transition

Use the actual repository behavior rather than forcing these exact flows if the existing implementation differs.

## Phase 4 — Extract Deterministic Instructions

Refactor the selected nodes so deterministic responsibilities are no longer expressed as instructions that an agent must interpret.

Prefer existing Foundry abstractions when they already represent the required behavior.

Where an appropriate abstraction does not exist, do **not** prematurely build the full future job system. Instead:

1. identify the missing deterministic concept,
2. give it a clear representation appropriate to the current architecture,
3. make the smallest change necessary to separate it from agent judgment.

Avoid speculative framework building.

The purpose of this refactor is to expose the requirements of the future execution engine, not implement that engine in advance.

## Phase 5 — Reduce Agent Markdown

After deterministic behavior has been extracted, review the remaining agent-facing Markdown.

It should primarily answer:

> What judgment does this agent need to perform?

Remove instructions concerned with:

- workflow navigation
- checking known runtime state
- printing UI elements
- receipts
- bookkeeping
- deterministic validation
- state transitions
- implementation details of orchestration

The remaining Markdown should be substantially smaller and focused on reasoning.

For Examination, for example, the agent instructions should focus on understanding the user's request, examining relevant context, identifying uncertainty, asking useful questions, and producing the expected examination result.

## Phase 6 — Report Architectural Discoveries

As part of the work, produce a short report describing the deterministic primitives discovered during the extraction.

For each candidate primitive, identify:

- what behavior it represents
- which nodes currently use it
- whether Foundry already has an implementation
- whether the implementation is adequate
- whether it appears to belong in node configuration, workflow configuration, engine code, or presentation code

This report will inform the next task: designing the durable job execution system.

Do not implement that system in this task.

## Constraints

Preserve existing behavior wherever practical.

Do not:

- redesign the entire CLI
- build a daemon/background service
- build the TUI
- implement job persistence
- introduce a large generalized workflow framework
- redesign every Foundry phase
- move judgment into deterministic code simply to eliminate Markdown
- convert genuinely semantic decisions into brittle rules

This work should make the existing architecture **simpler**, not introduce another abstraction layer around the existing complexity.

## Verification

After the refactor, demonstrate the separation using at least Intake and Examination.

For each node, show:

**Deterministic responsibilities**

What Foundry itself now owns.

**Agent responsibilities**

What judgment remains in Markdown.

**Presentation responsibilities**

What belongs to the eventual CLI/UI.

**Policy**

What controls admission, completion, failure, and transition.

Verify that an agent is no longer instructed to inspect or reason about deterministic state that Foundry already possesses.

Run the existing relevant tests and add focused tests where deterministic behavior has been moved into code/configuration.

## Deliverable

At completion I want:

1. The refactored Intake and Examination definitions/instructions.
2. Any minimal supporting code/configuration necessary for the extraction.
3. Tests demonstrating preserved deterministic behavior.
4. A before/after responsibility breakdown.
5. A list of reusable deterministic primitives discovered.
6. A list of unresolved cases where it is unclear whether something belongs to Judgment, Mechanism, Policy, or Presentation.
7. Recommendations for the **next** architectural step, without implementing that next step.

The most important success criterion is:

> An agent reading the remaining Markdown should only be receiving instructions for work that actually benefits from agent judgment.

Everything Foundry can know, check, execute, enforce, persist, transition, or present deterministically should be moving toward explicit runtime behavior rather than natural-language instructions.