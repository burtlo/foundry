---
step_id: shape.intake
title: Shape intake — validates inputs, prerequisites, and configuration
worker:
  prompt: registry:agents/intake-checker.shape.md
  contract: registry:contracts/intake-checker.shape.yaml
  mode: shape
state_keys:
  - ticket
  - run_slug
  - clarifying_questions
  - questions_asked_total
  - examination_round
  - open_clarifying_questions_count
---

## Purpose

Turn the user's work request into a normalized ticket packet the rest of the shape phase reads from. Validate that the application repository is bootstrapped and configured enough to proceed. Seal `ticket.json` and intake evidence, then route to `shape.examine`.

This step is the **flow entry** (`implementation` → `shape.intake`) and the **reshape on-ramp** when verify routes here with `loop: reshape`.

v1 accepts unstructured or semi-structured input only — **Jira intake is deferred**. Synthesize POC `intake.free_text`, `intake.local`, and `intake.jira` into one v1 step:

| Input channel | v1 handling |
|---|---|
| Inline chat (one-sentence feature + target area) | Steward confirms with user; `source_type: chat` |
| Pasted markdown ticket (frontmatter + body) | Steward normalizes to `ticket.json`; `source_type: paste` |
| Local markdown file under tickets root | Steward loads path user provides; `source_type: file` |
| URL reference | Steward captures URL in `source_ref`; `source_type: url` |
| Repo / workspace inference | Steward infers scope from open files or stated area; `source_type: repo_inference` |

**Git:** a clean working tree is **not** required at shape intake — WIP and untracked files may inform shaping ([v1-spec.md](../../docs/v1-spec.md#git-cleanliness)).

## Prerequisites

The engine admits the visit and runs lifecycle hooks before steward work opens:

| Hook | Check | Role |
|---|---|---|
| `on_open` | `validate-manifest` | Engine probe (`command: validate_manifest` → `foundry app validate`); **not** a steward `allow.cli` capability |

If `validate-manifest` fails, the visit does not open. Steward directs the user to `/craft-init` or manifest repair — do not bypass with `transition`.

On a **fresh run**, the user starts `/craft-shape` (or `foundry run create --flow implementation`). On **reshape**, the prior shape history remains; intake captures the updated work prompt and re-seals `ticket`.

## Inputs

**Reads (engine-supplied context per `factory-flow.yaml`):**

| Namespace | Keys |
|---|---|
| `config` | `workspace` |
| `state` | `ticket` (prior visit on reshape), `app_folder` |

**Human input (at least one required):**

- Work prompt: inline description, pasted content, file path, URL, or repo-scoped inference
- Target application repository (when not inferable from workspace)

**Reshape context (when `loop: reshape`):**

- Prior `approved_ac`, plan version, and verify notes from run state (read-only context for steward; not owned here)
- Updated user intent explaining what to reshape

## Steward actions

Execute in order while the visit is `opened`:

1. **Confirm the work request.** One turn when possible: restate what the user wants and the target repo/area. On reshape, confirm what changed since the last shape cycle.
2. **Resolve `app_folder`.** Order: user-stated area → single app repo in workspace → `config.workspace` default. Write to `state.app_folder` (`allow.state`).
3. **Capture `raw_input`.** Preserve the user's verbatim prompt (chat text, pasted body, file contents summary, or URL) for audit.
4. **Write `normalized_translation`.** Steward- and worker-produced summary: goal, constraints, target surfaces, and explicit out-of-scope notes when relevant. This is what downstream shape steps treat as the ticket body.
5. **Set ticket metadata.** Populate `source_type`, `source_ref` (nullable), and `issue_key` (nullable — always null in v1; no Jira keys).
6. **Draft `run:ticket.json`.** Write the working copy to a path under `allow.files.write` (see [Artifacts](#artifacts)).
7. **Launch `intake-checker.shape`** to assess work-request capture and manifest readability. Incorporate worker assessment into the intake receipt (see [Worker launch](#worker-launch)).
8. **Publish the ticket artifact:**

```foundry-invoke
artifact publish --artifact ticket --source run:ticket.json
```

9. **Seal receipts** (intake evidence + agent assessment). See [Receipts](#receipts). Use capability `receipt.link` (`foundry receipt seal`).
10. **Request close:**

```foundry-invoke
visit transition --summary "Intake complete"
```

The engine runs `on_seal` (`intake-receipt-sealed`). Failure → `reopen` (fix evidence, then `transition` again on the **same** visit).

## Worker launch

Launch the bound worker when manifest/bootstrap questions need agent verification beyond the engine's `validate-manifest` probe.

| Field | Value |
|---|---|
| Prompt | `registry:agents/intake-checker.shape.md` |
| Contract | `registry:contracts/intake-checker.shape.yaml` |
| Valid next state | `shape.examine` (contract `modes.shape.valid_next_states`) |

**Contract expectations (`intake-checker.shape.yaml`):**

- Capabilities: `intake`, `manifest_validation`
- Required output: `outputs.summary_markdown`
- Agent receipt schema: `registry:schemas/agent-receipt.schema.json` (steward seals; CLI owns `provenance`)

**Worker inputs (from steward / engine context):**

| Input | Source |
|---|---|
| `app_folder` | `state.app_folder` (resolved application repo root) |
| `work_prompt` | User work request for this intake |
| `draft_ticket` | Optional partial ticket from steward draft |
| `issue_key`, `labels` | Optional when user supplied them |

**Do not pass `checks[]` to the worker** (Path B). Build intake receipt `checks[]` from `check.recorded` on the ledger (`on_examine` + `on_open` on this visit) when assembling the intake receipt before seal. Use `foundry ledger show` or future `foundry check show` — see [check-lookup-cli.md](../../docs/transitions/check-lookup-cli.md).

**Worker responsibilities:**

- Synthesize ticket capture (`raw_input`, `normalized_translation`) — any present user input channel is sufficient
- Assess manifest readability under `app_folder` (broken references, builder/verification risks)
- Return `outputs.summary_markdown` and `blockers[]` for `agent_assessment` merge and agent receipt seal

**Blocked intake:** when the worker or steward judges the run cannot proceed, set intake receipt `status: blocked`, document `blocked_reason`, and **do not** call `transition` until the user resolves the blocker or aborts the run.

## Artifacts

### Declared output: `ticket`

| Field | Value |
|---|---|
| Logical id | `ticket` |
| Kind | `document` |
| URI | `run:artifacts/{visit_id}/ticket.json` (engine resolves `{visit_id}` before work opens) |
| Schema | `registry:schemas/ticket.schema.json` |
| Media type | `application/json` |

Publish via `artifact publish` only. The steward drafts content at `run:ticket.json` (or visit-scoped path); publication materializes the immutable artifact and appends `artifact.linked`.

### `ticket.json` fields (v1-spec §Run identity & artifacts)

| Field | Required | Meaning |
|---|---|---|
| `raw_input` | yes | Verbatim or faithful capture of user-supplied input |
| `normalized_translation` | yes | Steward/worker normalized summary for downstream shape steps |
| `source_type` | yes | `chat`, `paste`, `file`, `url`, or `repo_inference` (enum in `ticket.schema.json`) |
| `source_ref` | no | File path, URL, or ticket filename when applicable; otherwise `null` |
| `issue_key` | no | Always `null` in v1 (Jira deferred) |

**Path note:** [gaps.md](../../docs/cli-v1/gaps.md#8-receipt-and-artifact-paths) — the published artifact URI is authoritative (`run:artifacts/{visit_id}/ticket.json`). `run:ticket.json` is a draft/staging path in `allow.files.write`, not the ledger URI.

## Receipts

Two receipt schemas are required before seal:

| Schema | Purpose | Seal check |
|---|---|---|
| `registry:schemas/intake-receipt.schema.json` | CLI checks run, captured outputs, pass/fail per check, agent assessment overlay | `intake-receipt-sealed` on `on_seal` |
| `registry:schemas/agent-receipt.schema.json` | Worker completion evidence for `intake-checker.shape` | `agent-receipt-sealed` on `on_seal` |

**Intake receipt minimum content:**

- `step_id`: `shape.intake`
- `status`: `passed` | `blocked` | `failed`
- `checks[]`: at least one entry from ledger `check.recorded` (`on_examine` + `on_open` on this visit). Per-check `status`: `pass`, `fail`, `not_applicable`; optional `summary` / `evidence` from recorded probe output
- `agent_assessment` (when worker ran): `summary_markdown` from worker output; optional `blocked_reason` from worker `blockers[]`
- `inputs`: resolved `app_folder`, `source_type`, reshape flag when applicable

**Draft seal commands (walkthrough v-001):**

```foundry-invoke
receipt seal --schema registry:schemas/intake-receipt.schema.json --file run:receipts/intake.json
```

```foundry-invoke
receipt seal --schema registry:schemas/agent-receipt.schema.json --file run:receipts/agent.json
```

## State keys

Keys this step may write (`allow.state`):

| Key | Role |
|---|---|
| `ticket` | Mirror of published `ticket.json` for fast steward context |
| `app_folder` | Resolved application repository root for this run |
| `run_slug` | Run identity slug (derived at bootstrap; set when first known) |
| `clarifying_questions` | Listed for potential reshape reset (deferred — primary owner is `shape.examine`) |
| `questions_asked_total` | Examination counter (owned by `shape.examine`; reshape reset deferred) |
| `examination_round` | Examination round index (owned by `shape.examine`; reshape reset deferred) |
| `open_clarifying_questions_count` | Fast-lane routing scalar for `shape.examine` (reshape reset deferred) |

The engine also grants implicit `state.nodes.shape.intake.*` scope per [capabilities.md](../../docs/workflow-schema-v1/capabilities.md#defaults).

**Intake does not** initialize or resolve clarifying questions — that is `shape.examine`. After a successful examine, `open_clarifying_questions_count` should be `0`. Reshape behavior (incremental append vs full replacement) is deferred.

## Allowed CLI

Steward may invoke **only** these capability ids on this node:

| Capability id | Command (when implemented) | Use |
|---|---|---|
| `artifact.publish` | `foundry artifact publish` | Publish declared `ticket` artifact |
| `receipt.link` | `foundry receipt seal` | Seal intake and agent receipts (`receipt.linked` ledger events) |
| `transition` | `foundry visit transition` | Request visit close after artifacts and receipts are ready |

**Engine-owned (not steward CLI):**

| Check / probe | Command body | When |
|---|---|---|
| `validate-manifest` | `foundry app validate` | `on_open` |
| `intake-receipt-sealed` | receipt ledger filter | `on_seal` |

`transition` does not select the destination. After seal, the engine takes `shape.intake-to-shape.examine` → `shape.examine`.

## Invalid transitions

- Do **not** call Atlassian / Jira tools — Jira intake is not in v1.
- Do **not** invent an `issue_key`; `null` is valid.
- Do **not** create a feature branch or edit application code — that belongs to execute.
- Do **not** require a clean git tree at this step.
- Do **not** run `foundry app validate` as a steward command — the engine runs `validate-manifest` on `on_open`.
- Do **not** invoke CLI capabilities not listed in `allow.cli` (including `branch.create`, `build.*`, `gate decide`).
- Do **not** call `transition` before `ticket` is published and intake receipt is sealed — `on_seal` reopens the visit on failure.
- Do **not** skip the worker when manifest or bootstrap questions need agent verification — seal a `blocked` intake receipt instead of proceeding with `passed`.
- Do **not** route manually to `shape.present` or `shape.record` — examination and record gates are downstream.
