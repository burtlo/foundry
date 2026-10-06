# Foundry run execution: target architecture and contracts

Status: architecture reference, October 2026. Phases 0–7 in [phases/README.md](../../phases/README.md) implement the local host, durable `advance`, agent connection, user CLI (`shape`, `runs`, `status`, `attach`, `answer`, `decide`, `start`, `retry`, `cancel`), host protocol v1, and per-run `ledger.jsonl` with migration/recovery ([Phase 7](../../phases/07-append-only-ledger.md)). Remaining gaps (full transactional materialized-state replay, production agent HTTP without stub auto-accept, TUI/web) are called out in the phase index — not every paragraph below reflects shipped behavior yet. **Workflow-02 gap closure:** [plans/shape-execute-verify-gap-closure-plan.md](../plans/shape-execute-verify-gap-closure-plan.md).

## Product boundary

A developer initializes a repository, starts shaping a request, answers questions, reviews a plan, and later explicitly starts execution and verification. A persistent local host advances runs through deterministic work. It invokes a model only for declared judgment work and presents human decisions through the CLI. A CLI invocation may exit while a run continues. A developer can attach to a run to see progress and respond.

Keep the existing name **run** and the existing **visit** lifecycle. Do not introduce a parallel `Job` aggregate. The host is a process that executes runs; a run is the durable job. A visit is one node occurrence, including loops and retries. `admitted → examined → opened → closed → sealed` remains the node lifecycle. A separate run execution disposition says why automatic advancement stopped.

```
developer CLI ── local control protocol ── job host ── run engine
                                              ├── registry + checks + policy
                                              ├── ledger + snapshot + artifacts + receipts
                                              └── agent adapter ── model API
```

The host owns transitions, checks, persistence, retries, and presentation events. An agent receives an immutable request and returns a structured proposal. It cannot patch run state, publish artifacts, seal receipts, choose connections, or issue Foundry CLI commands. The host validates the proposal and performs permitted changes. Human approvals and questions are explicit run inputs.

## What exists today and what must change

| Existing concept | Keep or change |
|---|---|
| `factory-flow.yaml` nodes, checks, policies, connections | Keep as registry authority; add explicit deterministic operations and agent task bindings only where needed. |
| `run create`, visit admission, hook evaluation, transition, gate decision | Reuse behavior behind a single `advance` engine operation. Retire direct steward orchestration from the user path after parity. |
| `run context` packet and `reads` / `allow` | Reuse resolution rules; compile a narrower agent request from them. Do not send the entire steward packet by default. |
| `snapshot.json` with embedded ledger | **Shipped (P7):** new events append to `{run_dir}/ledger.jsonl` (fsync) before `snapshot.json` is atomically replaced; inline `ledger[]` remains for existing callers; `storage_version: 2` marks migrated runs. Recovery rebuilds inline ledger from `ledger.jsonl` when the snapshot is missing or behind the file — not full visit/state replay. |
| agent receipt and worker contract | Preserve provenance/evidence concepts; replace `recommended_next_state` as control input with a validated semantic result. Routing stays with the engine. |
| Cursor slash commands and steward node Markdown | Keep as compatibility during migration. Judgment prompts become task prompts; CLI work steps move to engine operations. |

The current Shape Intake is **not** purely deterministic: its worker proposes ticket fields and a semantic `PROCEED`/`BLOCKED` verdict. The target Intake becomes deterministic only after faithful input capture and manifest validation move into runtime operations, and request interpretation moves to Examination. Until then, Intake must retain an explicit agent boundary. Never silently turn a semantic verdict into a file-existence rule.

## Run execution state

Persist `run.status` for durable lifecycle (`running`, `paused`, `halted`, `definition_error`, `execution_error`, `completed`) as already documented. Add `run.wait` as an orthogonal, nullable boundary. An open visit can be `running` while waiting; a wait is not a failure.

| `wait.kind` | Why advancement stopped | Resume input |
|---|---|---|
| `agent` | A task has been durably dispatched or needs dispatch. | Validated result for that request. |
| `user_input` | Agent has one or more clarification questions. | Answers linked to question IDs. |
| `decision` | A user gate is open. | One declared option plus actor. |
| `operator` | An explicit halt/escalation/error requires intervention. | Authorized retry, resume, or cancel action. |

`wait` includes `id`, `visit_id`, `kind`, `created_at`, `request_ref`, and a safe display summary. `null` means the host may advance. A run is `completed` only when a terminal visit seals. `halted` and error statuses remain distinct from `wait.kind`; the CLI shows both status and reason. Avoid `WaitingForAgent` as a new durable run status, because it conflates ordinary asynchronous work with the existing run lifecycle.

## Advance contract

`advance(run_id)` is the only engine entry point that moves through nodes. It takes an exclusive per-run lock, reloads durable state, and repeats until it reaches a wait, halt, error, completion, or a bounded work budget. Each iteration executes in this order:

1. Reconcile any completed external result and pending durable operation.
2. Admit or resume the active visit; run the appropriate lifecycle hook checks in registry order.
3. Apply policy and persist the observed check, action, and changed position before any subsequent side effect.
4. Execute declared deterministic operations using idempotency keys scoped to run, visit, and operation.
5. If judgment is required, persist an agent request and `wait.kind=agent`, then dispatch. If human input is required, persist a question or decision request and wait.
6. Validate submitted output against the task contract and current visit; publish accepted artifacts/receipts and derived state through the engine.
7. Evaluate close/seal checks, seal once, select exactly one eligible connection, and continue. Never route before seal.

The outcome is `{run_id, revision, status, active_visit, wait, reason, events_after}`. Expected check failure uses the declared policy; an infrastructure failure uses `execution_error`; malformed or ambiguous routing uses `definition_error`. The host must never treat an agent's `BLOCKED` or `recommended_next_state` text as a transition. Repeating `advance` at the same revision is safe.

### Shape proof

**Target Intake:** capture the original request verbatim and durably, validate application manifest/configuration, create a ticket with the raw input and source reference, publish deterministic evidence, seal, and route to Examination. Missing input or invalid configuration stops with a structured reason and no model call. Do not require a polished `normalized_translation` to leave Intake; make it nullable or have Examination fill it. This requires a ticket schema migration.

**Target Examination:** build a bounded request from the ticket, relevant project files, config, and prior answers; ask the model to interpret the request, identify ambiguities, propose draft acceptance criteria and assumptions, and choose whether questions are needed. The engine validates the result and either records a `user_input` wait or persists the draft and seals. During migration, any `open_clarifying_questions_count` used for routing must be derived from structured question records, never patched by an agent. Align the final route with the exploratory [predicate language](predicate-language.md) if that design is adopted; query authoritative questions directly when possible.

## Agent connection contract

The workflow declares a **task**, not a provider or model. A task definition binds prompt text, input selection, output schema, allowed output artifacts, and budgets. Host configuration binds that task to an adapter/model. A task request is immutable after dispatch and has a digest of its exact input and prompt versions.

```json
{
  "protocol_version": 1,
  "request_id": "ar_...",
  "run_id": "...",
  "visit_id": "v-002",
  "task_id": "shape.examine",
  "attempt": 1,
  "definition_digest": "sha256:...",
  "input_digest": "sha256:...",
  "instructions": "Judgment-only instructions...",
  "input": {"ticket": {}, "project_context": [], "prior_answers": []},
  "output_schema": "registry:schemas/shape-examination-result.schema.json",
  "limits": {"max_input_chars": 24000, "timeout_seconds": 120},
  "capabilities": {"tools": [], "file_writes": false}
}
```

The host resolves `registry:`, `run:`, and `workspace:` references before invocation; it sends content or explicitly bounded references, never an ambient working directory or unrestricted tool access. Provider secrets remain in host configuration/environment and never enter run records or prompts. The adapter handles provider authentication, transport, retries, and response capture. A first adapter may use one direct model API; provider selection is host configuration, not workflow control flow.

The adapter returns an envelope `{request_id, attempt, provider_request_id, raw_response_ref, usage, finish_reason, result}`. `result` must validate against the task's strict JSON schema. For Examination, the minimum semantic result is:

```json
{
  "summary": "...",
  "draft_acceptance_criteria": ["..."],
  "assumptions": ["..."],
  "questions": [{"id": "q1", "text": "...", "why_needed": "..."}],
  "decisions": [{"text": "...", "basis": "..."}]
}
```

Question IDs must be unique within the request. The engine decides whether questions trigger a wait and how answers are stored. A validation failure can retry within a configured limit using the same immutable request plus a schema error; exhaustion pauses for operator review with raw response retained. A late or duplicate result is ignored unless its `request_id`, `attempt`, visit, and active wait match; acceptance is idempotent. A model timeout has an explicit retry policy. The host must not assume a network request is exactly once: after crash recovery it may repeat an uncertain call, but it must accept at most one result for the task attempt.

Legacy worker receipts become host generated evidence containing request/response digests, provider metadata, validated semantic result reference, status, and error/usage metadata. Avoid asking the model to fabricate receipt IDs, timestamps, provenance, check results, or recommended next state.

## Persistence and host protocol

One local host process owns a workspace's run mutations. Use a Unix domain socket for local CLI requests and a versioned JSON request/response protocol. The CLI can start the host on demand and reconnect; the host survives CLI exit. Host discovery uses a workspace-specific socket/lock under `.foundry/`, with owner-only permissions. On startup the host validates the registry version and recovers each nonterminal run. Run mutations require an expected `revision`; conflicts return current revision and state so stale clients cannot overwrite newer answers or decisions.

The storage transaction must commit the event and its state change together, or recover the snapshot by replaying committed events. **As implemented (P7):** `commit_snapshot` appends new ledger events to `ledger.jsonl` under the per-run lock, syncs inline `ledger[]`, then atomically replaces `snapshot.json`; load migrates legacy inline-only snapshots and can repair from `ledger.jsonl`. Host mutation idempotency keys persist in `.foundry/host/idempotency.json` (24h TTL, 1000-key cap). Record `run.created`, visit/check/policy events, `agent.requested`, `agent.result.accepted` or rejected, `user.input.requested`, `user.input.submitted`, and operation outcomes. A durable outbox record precedes an external model call; dispatch completion updates that record. Files for artifacts and raw responses are written to temporary paths, fsynced, then atomically renamed before linked in the ledger.

The control protocol has commands `health`, `run.create`, `run.get`, `run.list`, `run.events`, `run.advance`, `run.answer`, `run.decide`, `run.retry`, `run.cancel`, and `host.stop`. Every mutation has a client idempotency key and expected revision. Event streaming supports `after_seq` and reconnection; it need not use a terminal-specific protocol. The host serializes each run independently. A single local run at a time is sufficient for the first host release; multiple active runs can follow after locking and resource limits are proven.

## User CLI

CLI examples show the intended interface; final spelling should be checked in a short usability pass before implementation.

```text
foundry init                       # discover, preview, and write app/config setup
foundry shape --input "Add rate limiting"  # create a run and begin Shape
foundry shape --input-file "./plan.md"
foundry runs                       # list runs with phase, node, status, wait
foundry status [RUN]               # active run by default when unambiguous
foundry attach RUN                 # stream events; answer/decide from prompts
foundry decide RUN accept          # decision at the active user gate
foundry start RUN                  # explicit Shape → Execute authorization
foundry retry RUN                  # retry a recoverable error
foundry cancel RUN                 # stop a run with recorded reason
foundry host status|start|stop     # local service control
foundry status RUN --json          # stable machine output
```

`shape` persists the exact request before returning. `attach` displays a snapshot, then streams events by sequence; detach leaves the run running. `Ctrl-C` detaches and does not cancel. A prompt shows node, question/decision ID, allowed options, and why input is needed. Noninteractive commands fail with a typed `WAIT_KIND_MISMATCH` or `STALE_REVISION` rather than guessing. `start` is only valid at the existing Execute start gate after Shape is recorded. Keep low-level `visit`, `receipt`, `artifact`, and `ledger` commands under `foundry dev` or an internal namespace during compatibility; they should not be the normal user journey. `--json` emits one versioned envelope on stdout; diagnostics go to stderr. Exit codes distinguish usage, validation, conflict, host unavailable, and run failure.

## Invariants and deliberate limits

- Every run uses a pinned flow/registry digest, so a host upgrade cannot change routing mid-run without an explicit migration.
- Only the engine writes workflow state, receipts, artifacts, and transitions. Human inputs are attributed; agent outputs are evidence, not commands.
- Checks observe; operations mutate; policies choose actions. A check command may not perform setup.
- The first release is local and single host. Remote execution, distributed queues, TUI, and web UI are later concerns.
- The CLI is a client of the same host protocol used by future interfaces. It must remain useful without an interactive terminal through `--json` and direct answer/decision commands.
