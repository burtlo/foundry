# POC → v1 transitions

Reference for importing existing subagent prompts from the eval-foundry-approach POC into the v1 workflow registry. Use when asking an agent to port `.cursor/agents/*.md` and matching `workers/{worker-id}/contract.yaml`.

**Status:** judgment notes from the first port (`intake-checker`). Not a build spec — no tooling or automation is implied here.

**Also in this folder:**

- [steward-authoring.md](steward-authoring.md) — rules for writing `/craft-*` commands and `nodes/{node-id}/instructions.md` (engine vs steward domain, handoffs, anti-patterns)
- [command-bodied-checks.md](command-bodied-checks.md) — why `flow.checks` uses catalog indirection for `command:` probes, naming layers, and engine vs steward ownership
- [intake-checker.md](intake-checker.md) — intake worker design history (multi-mode archived; shape-only ships as `intake-checker.shape.md`)
- [check-lookup-cli.md](check-lookup-cli.md) — Path A′ draft (`check describe`, `check show`); not implemented

---

## Vocabulary (use the right term per layer)

Same concept, different audiences — avoid one phrase everywhere.

| Concept | Flow schema | Steward docs (`nodes/`, `steps/`) | Subagent prompt (`.cursor/agents/`) | Contract |
|---------|-------------|-----------------------------------|-------------------------------------|----------|
| Context at spawn | `reads` (+ visit ids; **Path B:** no `checks[]` on worker) | **worker context** — what to pass when spawning the worker | **Inputs** — field table; no doc links | — |
| Catalog check results | `check.recorded` on ledger | Build intake receipt `checks[]` when sealing (**Path B**) | *(not worker input)* | — |
| Work to perform | `worker.mode` | launch timing in steward sequence | **Task** (or **Instructions**) | `capabilities` (tags) |
| Structured result | `receipts` schemas | seal via `receipt.link` | **Output** | `required_output_fields` |

**Avoid in subagent prompts**

| Phrase | Why | Prefer |
|--------|-----|--------|
| Launch packet | Informal; not in workflow-schema-v1 | **Inputs** |
| Return to parent | Subagent should not model orchestration; Cursor Task returns a message to the invoker | **Output** |
| Your job | Fine colloquially; less standard in agent files | **Task** |
| Parent steward | Correct in v1-spec for phase agents; odd inside the child prompt | **invoker** or omit (inputs table is enough) |

**Cursor alignment:** `.cursor/agents/*.md` is the specialized instruction file. The **invoker** (phase steward agent, or a human) spawns via Task with runtime **inputs** appended to the prompt. The child file defines **Purpose → Inputs → Task → Output** — not routing, not registry paths.

**Output section:** prefer a fixed markdown **template** plus one filled **example** for `outputs.summary_markdown`. Use top-level `blockers[]` for machine-readable block reasons; verdict lives in the markdown header. **Path B:** no **Checks** section in worker output — steward owns receipt `checks[]`.

---

## Where things live in v1

| Artifact | Path | Audience |
|----------|------|----------|
| Flow registry (nodes, checks, `reads`, `allow`, worker binding) | `.cursor/foundry/flows/factory-flow.yaml` | Engine, validators, human authors |
| Worker prompt | `.cursor/agents/{name}.md` | **Subagent** (spawned by parent steward) |
| Worker contract | `.cursor/foundry/workers/{worker-id}/contract.yaml` | Engine, parent steward, receipt validation |
| Steward step instructions | `.cursor/foundry/nodes/{node-id}/instructions.md` | **Parent** steward at each node |
| Node reference (optional) | [docs/generated/nodes/{node-id}.md](../generated/nodes/) | Humans, parent stewards — **not** the subagent |
| Receipt schemas | `.cursor/foundry/schemas/*.schema.json` | CLI seal + validation |

Worker binding on a node:

```yaml
worker:
  prompt: registry:agents/intake-checker.shape.md
  contract: registry:workers/intake-checker.shape/contract.yaml
  mode: shape   # contract modes.<mode> when present
```

---

## Conversion checklist (POC → v1)

### 1. Strip POC-only surfaces

Remove or replace references that do not exist in v1:

| POC pattern | v1 replacement |
|-------------|----------------|
| `FactoryConfig`, `team-variables.md` | Dropped — context comes from engine `reads` and parent launch packet |
| `{app_folder}` template variable | `state.app_folder` — resolved application repo root; pass as `app_folder` in worker inputs (not `workspace`) |
| `craft_staging_path`, protocol 2.0/2.2.0 craft JSON | Dropped — steward seals `agent-receipt.schema.json` via `receipt.link` |
| `.cursor/foundry/docs/worker-launch-contract.md` | Not in v1 registry; launch packet is engine-/parent-assembled |
| `AGENTS.md` as a required read | Dropped unless parent explicitly includes content in launch packet |
| Telemetry section duplicating receipt fields | Fold into contract `required_output_fields` + agent receipt schema |
| `write_scopes: craft_staging_path` on readonly workers | Remove from contract when `readonly: true` |

### 2. Separate catalog checks from agent judgment

POC prompts often ask the subagent to verify things the workflow now expresses as **catalog checks** on lifecycle hooks (`on_examine`, `on_open`, `on_seal`).

**Path B (default for intake workers):** do **not** pass `checks[]` to the worker. The steward builds intake receipt `checks[]` from `check.recorded` on the ledger when sealing. The worker returns `agent_assessment` only (findings, verdict, ticket draft).

**Path A′ (future):** thin check ids + read-only `foundry check describe` / `check show` — see [check-lookup-cli.md](check-lookup-cli.md).

**Rule:** If `factory-flow.yaml` already has a check id for it, the engine owns pass/fail. The subagent does not copy or re-run catalog checks unless explicitly on Path A′ with `check show` (recorded output only, not `check eval`). Rationale for `command:` catalog entries vs bare CLI: [command-bodied-checks.md](command-bodied-checks.md).

Examples already in the implementation flow:

| Concern | Check id | Typical hook |
|---------|----------|--------------|
| Manifest valid | `validate-manifest` | `on_open` |
| Clean git (execute) | `validate-git-clean-execute` | `on_open` |
| Approved AC recorded | `approved-ac-recorded` | `on_examine` |
| Prior shape record sealed | `prior-shape-record-sealed` | `on_examine` |
| Verify prerequisites | `validate-verify-context` | `on_open` |

The subagent’s job is **synthesis** — manifest readability beyond schema validation, plan vs AC alignment, ticket field drafting, proceed/blocked judgment. Put that in `Assessment` and `blockers[]`, not in fake `checks[]` ids like `manifest_readability` or `agents_md`.

Intake receipt `checks[].status` uses catalog vocabulary: `pass`, `fail`, `not_applicable` (not `passed` / `skipped`).

### 3. Agent prompt vs parent steward vs node doc

Three audiences — do not collapse them into one file.

| Concern | Document |
|---------|----------|
| Lifecycle, ledger, permissions, artifacts, check definitions | [docs/generated/nodes/{node-id}.md](../generated/nodes/) or archived hand doc |
| Ordered steward actions, what to pass when launching worker | `.cursor/foundry/nodes/{node-id}/instructions.md` |
| Behavior, boundaries, output shape for the subagent | `.cursor/agents/{name}.md` |

**Subagent prompt rules (learned from `intake-checker`):**

- **No deep links** to node docs, `v1-spec.md`, or `factory-flow.yaml` — the subagent will not follow them.
- **No tables copied from** node `reads`, lifecycle hooks, or artifact declarations — the parent supplies a **launch packet** with resolved values.
- **Positive framing** — state what the worker does; avoid long “do not re-check X” lists for concerns already covered by engine checks. Mentioning checks the worker would not think to run adds noise and can mislead (same class of mistake as embedding routing targets).
- **Minimal guardrails** — `readonly`, inputs-only, return shape. Skip defensive prohibitions unless the task would naturally invite the wrong action.
- Keep the prompt **short**: inputs, mode-specific task, output template.

**Parent steward** (step instructions) owns:

- Intake receipt `checks[]` from ledger (`on_examine` + `on_open` for this visit) when sealing — **not** the worker
- Resolved `app_folder`, mode payload fields from node `reads`
- Merging worker `outputs.summary_markdown` into `agent_assessment`; sealing intake + agent receipts (`receipt.link`) before `transition`

### 4. Contract YAML

Port or create `workers/{worker-id}/contract.yaml` alongside the prompt:

```yaml
capabilities: [...]          # optional semantic tags
required_output_fields:      # must align with agent-receipt.schema.json
  - outputs.summary_markdown
modes:
  shape:
    valid_next_states:
      - shape.examine
```

- `valid_next_states` is for **parent/engine** when sealing the agent receipt (`recommended_next_state` on the receipt) — not for the subagent prompt. Routing after seal is `factory-flow.yaml` connections; the worker only reports proceed/blocked assessment and `blockers[]`.
- Add agent name to `agent-receipt.schema.json` `agent.name` enum when introducing a new worker.
- Contract fields are for validation and parent assembly — they can be summarized in step instructions; avoid duplicating the full contract inside the agent markdown body.

### 5. One prompt per intake role (prefer over multi-mode)

POC sometimes used one prompt with a `mode` switch (`shape` | `execute` | `verify`). That experiment is **archived** — see [intake-checker.md](intake-checker.md).

**Prefer:** dedicated files per role (`intake-checker.shape.md`, later `intake-checker.execute.md`, …) bound only to the matching node. Inputs match what that node’s steward actually passes; no `mode` field in the worker prompt.

When a worker truly serves multiple nodes with identical behavior, one file is fine. When tasks diverge (shape vs execute vs verify intake), split prompts.

### 6. Receipts and outputs

| Receipt | Role |
|---------|------|
| `intake-receipt.schema.json` | `checks[]` from ledger (steward) + `agent_assessment` from worker |
| `agent-receipt.schema.json` | Worker completion evidence; CLI owns `provenance` |

Worker returns payload fields; steward seals. Worker does not call `foundry receipt seal` or `visit transition`.

Common contract outputs for assessment workers: `outputs.summary_markdown`. Receipt ids and visit metadata are steward-owned at seal time.

### 7. Frontmatter

Keep YAML frontmatter compatible with Cursor subagent discovery:

```yaml
---
name: intake-checker.shape
description: >-
  One-line role summary for parent routing.
model: fast
readonly: true   # when worker must not edit repo
---
```

`description` is for the **parent** choosing when to spawn — not instructions for the child.

### 8. What to verify after a port

Manual review targets (no automated gate required yet):

- [ ] Node exists in `factory-flow.yaml` with `worker.prompt` + `worker.contract` + `worker.mode`
- [ ] Contract `modes` cover every binding mode
- [ ] `required_output_fields` exist on `agent-receipt.schema.json`
- [ ] Agent prompt does not duplicate checks already on the node lifecycle
- [ ] Agent prompt has no POC paths, `FactoryConfig`, or doc deep links
- [ ] Step instructions describe launch packet + receipt seal order (see generated node doc sequence when available)
- [ ] Regenerate node doc with `foundry dev docs` after registry changes

---

## Duplication problem (judgment notes — not actionable now)

Porting surfaces the same facts in many places: `factory-flow.yaml`, contract, step instructions, agent prompt, node doc, receipt schemas. That drift is the main maintenance risk.

**Direction agreed in discussion (defer implementation):**

1. **Source of truth** — `factory-flow.yaml` for node structure; `workers/{worker-id}/contract.yaml` for worker outputs and routing; receipt JSON Schemas for evidence shape.
2. **Generate variable facts** — launch-packet shape, steward “what to pass to worker,” and JSON Schema for packet fields should eventually be **derived** from the node binding, not pasted into every agent file.
3. **Keep agent markdown static** — behavior, judgment, boundaries, output section names. Do **not** codegen large `reads` / check tables into the subagent prompt; that bloats the child context and recreates the problem we removed from `intake-checker`.
4. **Path A′ CLI** — [check-lookup-cli.md](check-lookup-cli.md): `check describe` + `check show` for workers that need recorded failure detail without fat launch packets.
5. **Wait for pattern stability** — templating/codegen is premature until several more workers (examine, record, builder, validator) show what is shared vs role-specific.

**Practical rule until tooling exists:**

| Put changing variable facts here | Put stable behavior here |
|----------------------------------|---------------------------|
| `factory-flow.yaml` | `.cursor/agents/*.md` |
| `docs/generated/nodes/*.md` | Generated node reference (regenerate with `foundry dev docs`) |
| `.cursor/foundry/nodes/*/instructions.md` | |
| `workers/*/contract.yaml` | |

---

## Reference port: `intake-checker.shape`

First v1 worker ported from POC patterns; shape intake only. Multi-mode history: [intake-checker.md](intake-checker.md).

| Artifact | Path |
|----------|------|
| Prompt | `.cursor/agents/intake-checker.shape.md` |
| Contract | `.cursor/foundry/workers/intake-checker.shape/contract.yaml` |
| Steward step | `.cursor/foundry/nodes/shape.intake/instructions.md` |
| Node reference | [docs/generated/nodes/shape.intake.md](../generated/nodes/shape.intake.md) |

Use these as the tone and structure reference for the next imports.

---

## POC source location

Eval-foundry-approach clone (multi-root workspace):

- Agents: `{eval-foundry}/.cursor/agents/*.md`
- Contracts: may be monolithic or scattered — v1 uses one `contract.yaml` per worker under `.cursor/foundry/workers/{worker-id}/`
- Steps: `{eval-foundry}/.cursor/foundry/steps/*.md` — often split by intake channel; v1 consolidates per node (e.g. `nodes/shape.intake/instructions.md`)

When POC step count ≠ v1 node count, **synthesize** one steward file per v1 node from POC + `factory-flow.yaml` + `docs/v1-spec.md`; do not assume a 1:1 file mapping.
