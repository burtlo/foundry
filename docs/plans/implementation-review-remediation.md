# Foundry implementation review and remediation plan

Review date: 2026-10-06

Reviewed revision: `4d2c575` (`Implemented the final phase`)
Status: review findings and implementation plan; no fixes in this document.

## Scope and intended outcome

This review examines the implemented run engine, persistent host, agent connection, user CLI, tests, and automatic documentation generation. The intended outcome is a run that Foundry advances through deterministic work, uses model API calls only for declared judgment, survives client and host restarts, and can be shaped, started, observed, and controlled through the user CLI.

The top-level `init` command was intentionally removed by the user. Its absence is **not a finding** and this plan does not ask the implementer to restore it. Existing `app init` and `config init` commands remain available. See [parser.py](../../.cursor/foundry/cli/foundry_cli/parser.py#L364) and the generated [CLI index](../cli/index.md).

The architecture has useful foundations: deterministic Intake execution, explicit visits and waits, `advance`, JSONL ledger storage, revision checks, a host protocol, an agent task schema, high-level `shape/status/attach/answer/decide/start` commands, and a working documentation generator. The findings below identify where these pieces do not yet satisfy the full workflow and durability contracts.

## Test and documentation evidence

| Check | Result | Interpretation |
|---|---|---|
| `python -m pytest tests/unit -q` | 176 passed, 1 failed | [Host integration test](../../.cursor/foundry/cli/tests/unit/test_host_integration.py#L46) never observed the host as running under the default macOS pytest temp path. |
| Same host integration test with `--basetemp=/tmp/frytest` | 1 passed | Supports the Unix socket path-length diagnosis; it does not repair the host. |
| `python -m pytest tests/acceptance -q` | 95 passed, 5 failed | Two foreground host scenarios failed to start; three `dev` command scenarios failed because they ran the failing unit/acceptance suites. |
| `foundry dev all --quiet` | Failed | It runs the same failing suites. Its plain error output was `error [None]: None`, which obscures the underlying test failure; the direct pytest runs above expose it. |
| `foundry doc build --output <temporary directory> --json` | Succeeded; 81 pages generated | After normalizing line endings and output-path-dependent link targets, generated page content matched the tracked generated pages. This verifies generation consistency, not accuracy of authored descriptions. |

The acceptance feature currently checks that `shape` reaches Examination and that `start` works from a prepared gate fixture. It does not exercise a complete Shape path from a new request through clarification, presentation, approval, and recording. See [user_cli.feature](../../.cursor/foundry/cli/tests/acceptance/features/user_cli.feature#L13) and [job_host.feature](../../.cursor/foundry/cli/tests/acceptance/features/job_host.feature#L10). No measured statement or branch coverage percentage was collected; passing counts alone do not establish coverage of the failure paths below.

## Findings

### F1 — Shape stops at manual steward boundaries (P1)

**Observed:** After an Examination result is accepted and no questions remain, `advance` creates an operator wait instructing a steward to seal the agent receipt and transition. `shape.present` and `shape.record` are explicitly listed as manual steward steps. A developer cannot finish Shape using only the user CLI and host.

**Evidence:** [advance.py](../../.cursor/foundry/cli/foundry_cli/engine/advance.py#L153), [advance.py](../../.cursor/foundry/cli/foundry_cli/engine/advance.py#L197), [tasks.py](../../.cursor/foundry/cli/foundry_cli/engine/agent/tasks.py#L26), and the test expectation of an operator wait in [test_agent_connection.py](../../.cursor/foundry/cli/tests/unit/test_agent_connection.py#L133). The [Shape acceptance feature](../../.cursor/foundry/cli/tests/acceptance/features/user_cli.feature#L13) stops its new-run scenario at status/attach.

**Expected:** After valid judgment, Foundry creates and seals its own evidence, evaluates close/seal policy, and routes. Present and Record need declared task/operation boundaries and host-owned publication and transition. Human approval remains an explicit gate.

### F2 — Clarifying answers are not incorporated into a new judgment result (P1)

**Observed:** `answer` stores answers, marks questions answered, and clears the user-input wait when all are answered. Advancement then finds an already accepted Examination result and creates an operator wait. It does not issue a new agent request with those answers. Draft acceptance criteria can remain based on the pre-answer result.

**Evidence:** [examination_state.py](../../.cursor/foundry/cli/foundry_cli/engine/examination_state.py#L96), [submit.py](../../.cursor/foundry/cli/foundry_cli/engine/agent/submit.py#L130), [advance.py](../../.cursor/foundry/cli/foundry_cli/engine/advance.py#L153). The task builder does include prior question records, but it is not called again after the accepted result: [tasks.py](../../.cursor/foundry/cli/foundry_cli/engine/agent/tasks.py#L60).

**Expected:** Answers cause an explicit new Examination round or other declared semantic update. The new request carries the question/answer history, and the final draft records how answers changed scope, assumptions, and acceptance criteria. The engine derives unresolved-question state and routes after a valid final result.

### F3 — Normal execution uses a stub instead of a direct model API (P1)

**Observed:** The default adapter returns generic stub acceptance criteria. The optional HTTP adapter posts Foundry's request to a custom URL; it does not implement a provider's model API contract or select a configured model. This is useful for tests, but a normal user run can appear to have completed judgment without any model call.

**Evidence:** [adapter.py](../../.cursor/foundry/cli/foundry_cli/engine/agent/adapter.py#L28), [adapter.py](../../.cursor/foundry/cli/foundry_cli/engine/agent/adapter.py#L68), [http_adapter.py](../../.cursor/foundry/cli/foundry_cli/engine/agent/http_adapter.py#L15). The Examination input currently hard-codes `project_context: []`, so even a real adapter would lack selected repository context: [tasks.py](../../.cursor/foundry/cli/foundry_cli/engine/agent/tasks.py#L60).

**Expected:** A user-mode run must use an explicitly configured real model adapter or fail clearly before accepting judgment. Keep the stub restricted to test/development configuration. Define selected, bounded project context; provider credentials, transport, timeout, schema validation, and provenance. Do not put credentials in run records. A generic HTTP gateway can remain as an optional adapter if documented as such.

### F4 — External agent dispatch is not durably staged (P1)

**Observed:** `advance_run_durable` creates an agent request in memory, invokes the adapter, and may accept its result before `commit_snapshot` runs. A process crash during the external call can leave no durable record of the request or its outcome. Retrying may make another external call without a recoverable dispatch record.

**Evidence:** [run_service.py](../../.cursor/foundry/cli/foundry_cli/run_service.py#L235), [run_service.py](../../.cursor/foundry/cli/foundry_cli/run_service.py#L245), [run_service.py](../../.cursor/foundry/cli/foundry_cli/run_service.py#L282), [dispatch.py](../../.cursor/foundry/cli/foundry_cli/engine/agent/dispatch.py#L54). Startup recovery calls advancement again: [run_service.py](../../.cursor/foundry/cli/foundry_cli/run_service.py#L317).

**Expected:** Commit the immutable request and a pending outbox entry before any network call. Persist dispatch attempt and response references before applying the result. Define retry and uncertain-outcome semantics; accept at most one result per request/attempt/visit. Make timeout and malformed-output exhaustion inspectable.

### F5 — Ledger repair does not reconstruct a resumable run (P1)

**Observed:** If `snapshot.json` is missing or corrupt, `load_snapshot` calls `repair_snapshot_from_ledger`. That function restores ledger events and possibly run ID/revision, but not `active_visit`, run status, domain state, wait, config, or pending agent requests. If the JSONL file is ahead of a valid snapshot, the loader copies the events into the snapshot without applying their state effects. Thus the ledger is append-only evidence, but it is not currently sufficient to recover execution position.

**Evidence:** [ledger_store.py](../../.cursor/foundry/cli/foundry_cli/ledger_store.py#L133), [run_store.py](../../.cursor/foundry/cli/foundry_cli/run_store.py#L87), [run_store.py](../../.cursor/foundry/cli/foundry_cli/run_store.py#L109). Existing recovery assertions check event counts and revision, not the ability to advance the original run: [test_ledger_store.py](../../.cursor/foundry/cli/tests/unit/test_ledger_store.py#L84).

**Expected:** Either implement full replay of every state-changing event, or use a transactional/checkpoint design that makes the state required for resume recoverable. Do not treat a ledger-only shell as a valid runnable snapshot. Recovery must preserve current visit, wait, config, domain data, evidence links, and request state.

### F6 — Host socket path and single-owner behavior are fragile (P1)

**Observed:** The host binds a Unix socket inside the workspace. In the failing macOS test the resolved socket path was 142 characters; the host never became ready. The same test passed with a shorter `--basetemp` path. The server also unlinks an existing socket on bind, while `host_startup_lock` is held only during CLI spawn, not throughout server lifetime. Two foreground host processes can therefore contend for one workspace instead of having enforced single ownership.

**Evidence:** [server.py](../../.cursor/foundry/cli/foundry_cli/host/server.py#L81), [server.py](../../.cursor/foundry/cli/foundry_cli/host/server.py#L102), [host_commands.py](../../.cursor/foundry/cli/foundry_cli/host_commands.py#L35), [discovery.py](../../.cursor/foundry/cli/foundry_cli/host/discovery.py#L137), [test_host_integration.py](../../.cursor/foundry/cli/tests/unit/test_host_integration.py#L46), [job_host.feature](../../.cursor/foundry/cli/tests/acceptance/features/job_host.feature#L22).

**Expected:** Choose a short, stable socket location keyed by canonical workspace identity and keep metadata owner-only. Hold an exclusive ownership lock for the host's lifetime; never remove a live host's socket. Expose bind/start errors rather than silently discarding stderr in normal operation.

### F7 — Agent-facing and generated node descriptions still assign runtime work to a steward (P2)

**Observed:** Examination `judgment.md` tells the agent to use `allow.user.ask`, record state fields, ensure routing state, and summarize a receipt. The authored node `doc.yaml` and generated node page still describe state patches, ledger reads, receipt sealing, and transition by a parent steward. The generator reproduces this content faithfully, so regeneration alone will not correct it.

**Evidence:** [judgment.md](../../.cursor/foundry/nodes/shape.examine/judgment.md#L7), [doc.yaml](../../.cursor/foundry/nodes/shape.examine/doc.yaml#L4), [generated node page](../nodes/shape.examine.md), [operations.yaml](../../.cursor/foundry/nodes/shape.examine/operations.yaml). The operations file is loadable through [node_operations.py](../../.cursor/foundry/cli/foundry_cli/node_operations.py#L13), while the current `advance` path uses special-case Python handling and manual waits.

**Expected:** Judgment prompts describe only semantic work and the structured result. Authored node docs describe host-owned mechanics and actual waits. Generated docs are regenerated and reviewed after source updates.

### F8 — Host idempotency cache does not bind a key to its mutation (P2)

**Observed:** Handler dispatch looks up a cache entry by `idempotency_key` alone, then returns it before checking method or parameters. The store persists only the result under that key. Reusing a key for a different run or method can return an unrelated success/error. The current tests check repeated identical calls, not conflicting reuse.

**Evidence:** [handlers.py](../../.cursor/foundry/cli/foundry_cli/host/handlers.py#L65), [handlers.py](../../.cursor/foundry/cli/foundry_cli/host/handlers.py#L101), [idempotency_store.py](../../.cursor/foundry/cli/foundry_cli/host/idempotency_store.py#L70), [test_host_idempotency_store.py](../../.cursor/foundry/cli/tests/unit/test_host_idempotency_store.py#L30).

**Expected:** Persist method and a canonical request digest with each key. Replays of an identical mutation return the prior result; reuse with different content returns a typed conflict. Coordinate cache writes under a lock or transaction when the threaded host accepts concurrent clients.

### F9 — Shape input is trimmed before it is stored (P2)

**Observed:** Both `--input` and `--input-file` pass through `.strip()`, and advancement strips the stored prompt again. Leading or trailing whitespace and newlines in a pasted request or file are lost despite the CLI describing the input as verbatim. This can matter for pasted code, structured examples, and exact source provenance.

**Evidence:** [user_cli.py](../../.cursor/foundry/cli/foundry_cli/user_cli.py#L44), [advance.py](../../.cursor/foundry/cli/foundry_cli/engine/advance.py#L40), and the `Verbatim shape request text` help in [parser.py](../../.cursor/foundry/cli/foundry_cli/parser.py#L382).

**Expected:** Validate non-emptiness using a trimmed view, but persist and publish the original bytes/text. Define newline/encoding behavior for `--input-file`; test exact round trips through run creation, restart, and ticket publication.

## Ordered implementation plan

### 1. Stabilize host startup and the test gate

- Fix long-path socket selection and lifetime ownership.
- Preserve startup diagnostics so failed detached hosts have an actionable error.
- Re-run unit and acceptance suites under the default macOS temp directory; do not rely on a short `--basetemp` workaround.

**Acceptance:** Host startup, detach, restart, and two-client ownership tests pass at both short and long workspace paths. Unit and acceptance suites pass without the host-related cascade.

### 2. Make durable run and agent boundaries truthful

- Select a recovery design and implement full resume-state reconstruction or transactional state commit.
- Commit agent requests before dispatch; persist attempt/response outcomes and reconcile uncertain calls.
- Bind idempotency keys to a canonical mutation and serialize conflicting updates.

**Acceptance:** Crash-injection tests pass before/after ledger append, snapshot replace, request commit, network dispatch, response persistence, and result acceptance. Each recovered run retains its exact position and can advance without duplicating a seal, route, receipt, or accepted result.

### 3. Complete the judgment and Shape path

- Configure one real model API adapter for user runs and make unavailable configuration explicit. Keep the stub in test/development mode only.
- Provide bounded, selected repository context to Examination.
- Resume semantic work after clarification answers and have the host create receipts, seal visits, and route.
- Implement Present and Record as declared task/operation sequences. Keep user gates explicit.
- Remove remaining runtime commands and bookkeeping from agent-facing prompts.

**Acceptance:** A new request can reach a reviewed and recorded Shape plan through only user-facing commands, for both zero-question and multi-round clarification paths. Accepted output reflects the user's answers. No operator wait is used merely for receipt or transition mechanics.

### 4. Expand execution only after Shape is proven

- Audit Execute and Verify nodes for manual waits and legacy steward commands using the same boundary rules.
- Preserve explicit `start` authorization, declared checks, human gates, retry limits, and durable evidence.
- Do not mark the full run workflow complete until an end-to-end Execute/Verify path passes through the host.

**Acceptance:** A developer can start, attach, inspect, answer/decide, and complete a run through the user CLI. The host owns deterministic commands and transitions; model results cannot choose routes or bypass gates.

## Required test work for the implementer

Before changing each area, **define the unit and integration tests that establish its contract**, including setup, observable result, failure mode, and restart behavior. Add them with the implementation; do not only adjust tests to match current operator waits.

Minimum test set:

- Unit tests for wait transitions, question rounds, result/visit matching, task schema rejection, exact context selection, host idempotency conflicts, and ledger/state reconstruction.
- Unit and integration tests proving verbatim shape input survives run creation, restart, and ticket publication.
- Integration tests with separate CLI and host processes for long workspace paths, one-host ownership, client detach/reconnect, host restart, stale revisions, uncertain model dispatch, duplicate responses, and full Shape completion.
- A controlled fake model adapter for deterministic tests plus a separate provider contract/smoke test that proves the real adapter's request and response mapping without exposing credentials.
- Crash-boundary tests that fail at each durable-write boundary and then start a fresh process to inspect and advance the run.
- Acceptance scenarios from a clean application workspace, including a no-question path, a question/answer/revised-AC path, rejection/refinement, plan recording, and explicit Execute start.
- A documentation generation check that regenerates pages in their canonical location or compares content independent of output-directory links, then fails on unexpected tracked diffs.

Record the suite counts after repair and, if coverage tooling is adopted, report statement/branch coverage for the engine, host, storage, and agent adapter. Coverage percentage is supplemental to the scenario requirements above.

## Required documentation work for the implementer

Update the hand-authored sources **and** regenerate their outputs. At minimum review the flow registry, node `judgment.md` and `doc.yaml`, task/operation contracts, CLI annotations, README, concepts for engine/run record/visits/control plane, and the generated node/CLI/flow pages. Document:

- The supported CLI commands as actually shipped, respecting the user's removal of top-level `init`.
- The real adapter configuration, credentials location, fallback/error behavior, model request/result schema, and context selection.
- Durable wait/status semantics, retry and crash recovery guarantees, event/outbox ordering, and host ownership.
- How a user answers questions, approves a plan, starts Execute, attaches/detaches, and interprets failures.
- Any intentionally manual or unsupported node, labeled as such rather than described as fully automated.

Run `foundry doc build` or `foundry dev docs`, review the generated diff, and keep authored and generated content synchronized. The current generator works, but its Examination source still narrates steward CLI operations.
