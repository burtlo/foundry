# Remaining workflow nodes: orchestrator command and delivery plan

Status: implementation instruction, 2026-10-06. This document directs the next implementation effort; it does not claim that the remaining nodes work today.

## Mission and source of truth

Complete the Foundry workflow from Shape through Execute, Verify, and its declared terminal node. The persistent host must own deterministic operations, evidence, gates, routing, and recovery. A model task may supply bounded judgment through a configured model API, but must not impersonate the engine, select an undeclared route, or perform hidden lifecycle work. The user CLI must support initiating, observing, answering, deciding, starting, attaching to, and finishing runs according to the graph. `deliver.stub` is the completed handoff boundary: Foundry may finish with a short message that the verified work is ready for the user. Pushing the branch and any later delivery tasks belong to the user and are outside this workflow. Keep the intentionally removed top-level `init` command removed; `app init` and `config init` remain.

Read these sources before changing contracts:

- [Flow registry](../../.cursor/foundry/flows/factory-flow.yaml), especially nodes at lines 105–908 and connections at lines 909–1193.
- [Graph contract](../concepts/graph.md), especially the exact-one route rule at lines 188–216, and [control-plane contract](../concepts/control-plane.md).
- [Implementation review and remediation plan](implementation-review-remediation.md), including F1–F9 and its test and documentation requirements.
- [Current engine advancement](../../.cursor/foundry/cli/foundry_cli/engine/advance.py), [routing](../../.cursor/foundry/cli/foundry_cli/engine/routing.py), [hooks](../../.cursor/foundry/cli/foundry_cli/engine/hooks.py), [gate handling](../../.cursor/foundry/cli/foundry_cli/engine/gates.py), and [agent task binding](../../.cursor/foundry/cli/foundry_cli/engine/agent/tasks.py).

The flow declares **29 nodes and 39 connections**. The current runtime is a Shape slice, not an implementation of every declared node. Treat registry prose and generated pages as proposed behavior until executable contracts and tests confirm them.

## Copy-ready command for the orchestrator agent

> Work through `docs/plans/remaining-nodes-orchestrator-runbook.md` in its stated order. First review the graph and record contract decisions for every preimplementation blocker. The missing instruction files were never authored: design them from each node's actual behavior, review and implement every check they depend on, and add host or CLI tooling commands where the contracts require them. Resolve and independently verify the shared engine, host, agent, and Shape prerequisites before building Execute or Verify nodes. For each delivery slice, assign one implementation agent and a **different verification agent**. Give the implementation agent the contract worksheet, acceptance criteria, unit and feature/integration tests, and authored and generated documentation obligations. After the implementation agent reports completion, give the verification agent the original contract and actual diff without relying on the implementer's success claim. The verifier must review behavior and documentation, run focused and full required gates, exercise the stated failure and recovery paths, and return evidence and findings. Send findings back to the implementation agent; repeat verification until accepted. Do not advance to a dependent slice while a blocker remains. Record the final contract, test results, documentation generation result, and residual limitations for each slice. Finish with an end-to-end fresh-workspace run, restart/reattach and loop scenarios, and an independent final verification. Treat `deliver.stub` as the completed handoff to the user; do not add branch pushing or further delivery work to this workflow. Do not silently change gate semantics or permit a missing route.

The orchestrator owns scope, sequencing, decisions, and final acceptance. The implementation agent writes code, tests, registry definitions, and documentation. The verification agent is independent: it reads the registry and diff, tests observable behavior, checks evidence/recovery, and can reject delivery. Agent names or process mechanics may vary; the two roles must be separate for each slice.

## Step 0 — Establish the baseline and decisions

1. Save revision, working-tree status, baseline test outputs, and generated-doc diff. Preserve preexisting user changes. Do not reset the tree to make a gate pass.
2. Inventory every node's declared reads, writes, checks, operations, task binding, gate decider, outcomes, and outgoing connections. Review **every** declared check for purpose, input, timing, implementation, observable evidence, failure semantics, and test coverage. Inventory existing host/CLI commands and identify commands or operations the new node instructions will need. Compile references and route coverage before implementation. A declaration that points to a missing file is a design task and a validation error until resolved.
3. Write a decision record for each issue below. For a policy choice, specify the selected behavior and a testable reason before coding. The verification agent reviews the decisions against the graph contract.
4. Convert the review findings F1–F9 into tracked prerequisite work. Resolve their implementation and coverage requirements, including the default-path host failure, before the Execute/Verify work starts.

### Blocking issues found in the current workflow

| Issue and evidence | Required contract decision or repair before node implementation |
|---|---|
| Twelve `registry:steps/...` instruction references for `execute.intake`, `execute.branch`, `execute.plan`, `execute.build`, `execute.test`, `execute.commit`, `verify.intake`, `verify.acceptance`, `verify.code_quality`, `verify.code_review`, `verify.complete`, and `deliver.stub` have never had backing files. See [flow lines 385–906](../../.cursor/foundry/flows/factory-flow.yaml#L385). | Author each node's instructions from its refined contract. Decide which actions are deterministic operations, which need judgment, and which new host/CLI commands are required to carry them out. Add task/result schemas and tooling with tests as needed. Registry validation and doc generation must reject unresolved references. |
| `shape.record.gate` declares `hold`, but its sole connection covers `accept`. See [gate](../../.cursor/foundry/flows/factory-flow.yaml#L344) and [connection](../../.cursor/foundry/flows/factory-flow.yaml#L1039). | Define whether `hold` is a persistent user wait or a route to refinement, and represent it without violating exact-one route coverage. Test both decisions. |
| Four declared command checks (`validate_git_clean_execute`, `validate_verify_context`, `ensure_execution_graph_reference`, `validate_build_exit`) currently pass by default because only `validate_manifest` is implemented. See [registry](../../.cursor/foundry/flows/factory-flow.yaml#L34) and [hooks.py](../../.cursor/foundry/cli/foundry_cli/engine/hooks.py#L14). | Review **all** registry checks, including expression checks, for correctness and coverage. Implement the missing read-only command checks and typed failure/unknown-command handling. Define input, evidence, exit status, and timing for each. Revise or add checks when new node contracts require them. Unknown checks must fail closed. |
| Unknown `when` expressions currently evaluate false, and routing picks the first eligible connection. See [routing.py](../../.cursor/foundry/cli/foundry_cli/engine/routing.py#L40) and [routing.py](../../.cursor/foundry/cli/foundry_cli/engine/routing.py#L85). This conflicts with [graph.md](../concepts/graph.md#L188). | Implement the declared expression grammar and strict boolean/errors, plus static route coverage and runtime exactly-one selection. Zero or multiple eligible routes must yield `definition_error` with no new visit. |
| Advancement waits for user decisions at every gate, while `decide_gate` only permits `decider: user`. See [advance.py](../../.cursor/foundry/cli/foundry_cli/engine/advance.py#L122) and [gates.py](../../.cursor/foundry/cli/foundry_cli/engine/gates.py#L13). | Define an engine gate resolver that derives each decision from sealed, typed evidence and declared rules; seal and route atomically. User commands must not decide engine gates. Missing or contradictory evidence must halt with an actionable error. |
| The agent path is special-cased for `shape.examine`; Present and Record use operator waits, and operation YAML is loaded without a generic executor. See [advance.py](../../.cursor/foundry/cli/foundry_cli/engine/advance.py#L153), [tasks.py](../../.cursor/foundry/cli/foundry_cli/engine/agent/tasks.py#L23), and [node_operations.py](../../.cursor/foundry/cli/foundry_cli/node_operations.py). | Implement a generic node task/operation sequence with declared inputs, output validation, deterministic operation ownership, and host-owned receipts/transition. Resolve clarification rounds and complete Shape first. |
| Model dispatch, durable recovery, idempotency, host ownership, default stub behavior, and verbatim input have known gaps. See [review F2–F9](implementation-review-remediation.md#findings). | Complete the earlier remediation plan's tests and guarantees. A passing happy path does not close these issues. |
| `execute.start` still asks users to invoke `/craft-execute` in a new chat. See [flow line 377](../../.cursor/foundry/flows/factory-flow.yaml#L377). | Make its prompt and generated docs describe the shipped host/CLI transition. Preserve explicit user authorization to start Execute. |
| Engine gate classifications (`pass`/`repair`; `pass`/`replan`/`reshape`/`rework_execute`) and loop limits are declared without a fully specified evidence-to-decision rule. See [Execute/Verify gates](../../.cursor/foundry/flows/factory-flow.yaml#L570) and [loop checks](../../.cursor/foundry/flows/factory-flow.yaml#L94). | Define precedence, ownership, counting, and exhaustion behavior. Specify how a finding maps to repair, replan, reshape, or rework; require typed findings with evidence. Test each route and limit boundary. |
| `verify.code_quality` can seal `not_applicable` and skip its gate when review is disabled. See [connections](../../.cursor/foundry/flows/factory-flow.yaml#L983). | Confirm and document whether code review also remains active when quality review is disabled. Test both configurations and exact route selection. |
| `deliver.stub` is terminal, and the later Deliver phase has not been defined. See [flow line 901](../../.cursor/foundry/flows/factory-flow.yaml#L901). | Treat arrival at this sink as delivered for the current workflow. Record terminal completion and show a short, accurate handoff message with the branch/commit and verified result when available. Do not push the branch or perform later delivery tasks. Document that the user takes over from here. |

Do not substitute an agent's free-form assessment for a machine gate's missing rule. If a policy genuinely needs judgment, bind a typed model result to a step first; the gate then deterministically maps that sealed result to a declared option.

**Step 0 acceptance:** all policy decisions are written; every check and required command has a reviewed contract and implementation owner; missing instruction references are catalogued for their delivery slices; graph paths are statically valid where decidable; and the verifier can reproduce the baseline and review the proposed contracts. Unresolved references remain blocking for their slice and for final documentation generation.

## Step 1 — Implement and verify shared runtime prerequisites

Delivery order within this step:

1. Fix host path/ownership and make default-path tests reliable; retain useful startup diagnostics.
2. Make snapshot, ledger, outbox, agent dispatch, and idempotency recoverable and single-effect across crashes and retries.
3. Implement strict registry/reference validation, expression evaluation, observational checks, outcome handling, and exact-one routing.
4. Implement user and engine gate lifecycles, typed evidence, decision provenance, and loop counters.
5. Implement the generic task and operation executor and configured model API adapter. Keep test stubs explicit. Restrict agent input to declared, bounded context and validate outputs before state mutation.
6. Close Shape end to end, including answer-driven re-examination, Present, Record, their user gates, and `execute.start`. Remove lifecycle commands from judgment prompts and stale steward descriptions from authored docs.

**Acceptance:** a fresh run completes Shape through the user CLI; both zero-question and multi-round cases work; reject/hold paths behave as decided; no operator wait exists for host-owned bookkeeping; restart at each durable boundary resumes once; engine gates and routes obey the graph contract; and the independent verifier accepts the tests and generated documentation. See [review acceptance requirements](implementation-review-remediation.md#ordered-implementation-plan).

## Step 2 — Build nodes in dependency order

For **each** row below, perform the same four passes in order: **review** the current registry and runtime; **refine** a written node contract and tests; **implement** code, schema, docs, and tests; **verify** independently. Revisit the contract if verification finds an ambiguity. A row is complete only when its stated routes, failure cases, documentation, and feature scenarios pass. Preserve node identifiers unless a documented graph migration requires a change.

| Slice | Nodes, in delivery order | Contract and acceptance focus |
|---|---|---|
| 2A — Execute entry | `execute.intake` → `execute.intake.gate` → `execute.branch` → `execute.plan` | Check frozen Shape inputs, git cleanliness and branch ownership; define re-entry after verification; create/validate execution graph and plan evidence. Test failed intake, branch collision or dirty tree, restart, and the `pass` gate. No model may create a branch directly. |
| 2B — Build/test/repair | `execute.build` → `execute.test` → `execute.test.gate` → `execute.repair.limit.gate` | Define bounded implementation task input, patch/output provenance, deterministic test command selection, captured logs and exit codes, test-to-gate decision mapping, repair context and loop count. Test passing work, failing test, successful repair, exhausted limit, malformed result, and restart mid-attempt. |
| 2C — Commit handoff | `execute.commit` → `execute.commit.gate` | Define branch, index/worktree policy, commit authority, final SHA and receipt; verify clean/dirty behavior and Git failure. Ensure the gate checks actual commit evidence before Verify opens. |
| 2D — Verify entry and acceptance | `verify.intake` → `verify.intake.gate` → `verify.acceptance` → `verify.acceptance.gate` | Validate Execute context and independently compare delivered behavior with approved criteria. Produce itemized evidence and typed findings. Define deterministic mapping to `pass`, `replan`, `reshape`, `rework_execute`; test every route, especially return to earlier phases with retained/superseded artifacts. |
| 2E — Quality and human review | `verify.code_quality` → `verify.code_quality.gate` → `verify.code_review` → `verify.code_review.gate` | Check review-enabled skip policy, quality command evidence, `pass`/`repair`, and user `accept`/`reject`/`reshape`. Expose a concise review packet through status/attach; test disabled review, rejection repair, reshape, and authorization. |
| 2F — Completion boundary | `verify.complete` → `verify.complete.gate` → `deliver.stub` | Record verified completion evidence and explicit final user acceptance. Mark the run delivered at the terminal sink and show a concise handoff message. Test terminal status, branch/commit information when available, retained artifacts and events, attach/read behavior, and restart after completion. Do not push or undertake later delivery tasks. |

The repair route from code quality or human review converges on `execute.repair.limit.gate`; the acceptance `replan`, `reshape`, and `rework_execute` routes return to earlier slices. Once the forward path works, run these loops as an integrated slice. Recheck stale evidence, state revisions, limits, and artifact ancestry on every return. See [connections at lines 1063–1193](../../.cursor/foundry/flows/factory-flow.yaml#L1063).

## Node contract worksheet required before implementation

The implementation agent submits this for every node or tightly coupled step/gate pair. The verifier signs off on it before accepting code:

1. **Identity and entry:** node ID/kind, predecessors, admissible prior outcomes, visit identity, required state/config/artifacts, and source of each input.
2. **Authority:** which actions are host operations, model judgments, or explicit user decisions; exact CLI capability and actor allowed for each.
3. **Task contract:** when a model is needed, task ID/version, context selection and limits, provider/model configuration, request/result schema, result validation, timeout, retry, and provenance. If no model is needed, say so.
4. **Operation and tooling contract:** command or operation ID, whether existing tooling suffices or a new host/CLI command is needed, inputs, working directory, allowed file/state writes, idempotency key, side effects, output schema, receipt and log references, failure and restart behavior. New commands require help text, docs, unit tests, and a user-visible feature/integration scenario when applicable.
5. **Lifecycle and check contract:** every check at open/examine/close/seal, its reason, input, evaluation point, observable evidence, failure semantics and tests; artifact completeness, exact event order, seal outcome, wait types, and whether a user sees a decision or input request.
6. **Routing:** table for every routable outcome and every declared gate option, including condition evaluation, target, loop label, and zero/multiple-match error behavior.
7. **Tests and docs:** unit tests for the rule, process integration/feature scenarios for user-visible behavior, failure and recovery cases, authored docs changed, generated pages checked, and an observable acceptance command/result.

Do not hide work behind an `operator` wait or an instruction telling an agent to call low-level steward commands. Any intentionally manual action must be explicit, user visible, and covered by a declared capability.

## Implementation/verification handoff for every slice

**Implementation agent assignment:** include the slice, worksheet, decision records, related F1–F9 findings, source links, expected user path, required test cases, and documentation sources. Ask the agent to review/create missing instructions, review/implement every applicable check, and define any new tooling commands. It must define unit and integration/feature tests **before or alongside code**. It must report changed files, behavioral decisions, exact test commands/results, generated documentation changes, and unresolved risks. It may not mark its own slice verified.

**Verification agent assignment:** provide the same original contract plus the diff and implementation report. Ask it to inspect code and generated docs, run focused tests and relevant full gates, examine a fresh-workspace user path, force at least one failure and one restart boundary, and check routes and evidence against the registry. It reports `accepted` or `changes required`, with file/line findings and reproducible commands. Tests that only mirror the implementation are insufficient. The orchestrator sends findings to the implementer and requests a new independent verification pass after repairs.

**Slice exit:** contract settled; all declared references exist; unit and feature/integration tests pass; no unexplained regression in full suites; generated docs match authored source; CLI help and user docs match the behavior; verification agent accepts. Record revision and test evidence before starting the next dependent slice.

## Commands and evidence gates

Run from the repository root. Use the repository's own virtual environment or equivalent installed environment; do not rely on shortening pytest's temp path to conceal the host defect. Capture exit codes and logs for the handoff.

```sh
git status --short
.cursor/foundry/cli/.venv/bin/python .cursor/foundry/cli/foundry.py dev unit --quiet
.cursor/foundry/cli/.venv/bin/python .cursor/foundry/cli/foundry.py dev acceptance --quiet
.cursor/foundry/cli/.venv/bin/python .cursor/foundry/cli/foundry.py dev docs
git diff -- docs .cursor/foundry
```

Run focused pytest cases while iterating, then the full commands above at each slice exit. The `dev docs` command writes catalog indexes and generated documentation; inspect the resulting diff rather than assuming a successful build means the prose is correct. At final acceptance, run a clean-workspace end-to-end feature test through Shape, Execute, Verify, and the declared terminal behavior, then rerun after host restart and through each feedback route. Update [acceptance features](../../.cursor/foundry/cli/tests/acceptance/features/) and their [README](../../.cursor/foundry/cli/tests/acceptance/README.md) as coverage expands.

## Final orchestrator acceptance

The implementation is complete only when a developer can initiate and finish the declared workflow through the supported CLI, inspect and attach to runs, provide needed answers and decisions, and recover across restarts without duplicate effects. Every node has an executable contract and authored instructions, every check has been reviewed and tested, required tooling commands exist, every route and loop has a tested outcome, deterministic checks fail closed, model calls are explicit and bounded, feature tests cover the user journey and adverse paths, and authored plus generated documentation describe the shipped behavior. Reaching `deliver.stub` marks the work delivered in this workflow and gives the user a brief handoff to push the branch or take any later action they choose. The independent verifier must report acceptance with reproducible evidence.
