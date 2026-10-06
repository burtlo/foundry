# Phase 0 — Baseline and responsibility inventory

## Purpose

Establish actual behavior before changing execution. Focus on Shape Intake, Examination, their transition, and the Examination gate.

## Delivery steps

1. Run current unit and Shape acceptance tests and record results.
2. Inventory every instruction in selected node Markdown and worker prompts: file/line, behavior, Judgment/Mechanism/Policy/Presentation, current owner, proposed owner, and intended change.
3. Trace run creation, admission, hooks, receipt/artifact publication, transition, and routing through code and registry.
4. Record gaps between concept docs and implementation, especially inline ledger storage, direct snapshot writes, default-pass command checks, and chat-only work_prompt.
5. Decide which Intake work is semantic judgment and which is deterministic capture or validation.

## Expected deliverables

A checked-in responsibility inventory, current-flow trace, primitive list, unresolved cases, Intake/Examination boundary decision, and baseline test results.

## Acceptance criteria

- Every selected instruction has exactly one primary classification and proposed owner.
- Successful and failed Intake and the Examination question path are traced to actual code and declarations.
- The report marks documented guarantees that are not implemented.
- Baseline test failures are distinguished from new failures.
- No runtime behavior changes.

**Handoff:** Phase 1 uses the inventory as its change list.
