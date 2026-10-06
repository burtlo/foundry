# Workflow node revision — learned patterns (for implementers)

**Audience:** Implementer subagents on the node-revision orchestration track.  
**Orchestrator:** Updates this file as slices land; always read before starting a new `NODE_ID`.

## Process

1. **Implementer** — Review + plan + implement + targeted tests. **Never `git commit`.**
2. **Orchestrator verifier** (separate sub-chat, not nested under implementer) — Re-check plan, run tests, fix small gaps, **one scoped commit**, exclude junk paths below.

## Classify the node first

| Kind | Typical decider | Steward / host | Schema shape |
|------|-----------------|----------------|--------------|
| **User gate** | `user` | Two-turn UX (presentation → `gate decide` or `start`) | `instructions.md`, `reads` for display, `allow.user.decide` only |
| **Engine gate** | `engine` | `run advance` only; no `gate decide` | `instructions.md` explaining engine path; optional `reads.intake_receipt` in context |
| **Engine-owned step** | none | Blurb in `run context` markdown; host `run advance` | No `worker`, no flow `instructions`; `nodes/{id}/doc.yaml` + `operations.yaml` (authoring) |
| **Judgment step** | task worker | `run.agent.submit` + semantic `visit.*.complete` | `judgment.md`, `tasks/{id}.yaml`, result schema; narrow `allow.cli` |

**Step 6 rule:** Default to **A (fully deterministic)** until evidence forces **B (one bounded judgment)**. Avoid **C** unless the existing implementation truly needs broad discretion.

## Files to touch (checklist)

- `.cursor/foundry/flows/factory-flow.yaml` — minimal node block only
- `.cursor/foundry/nodes/{NODE_ID}/` — `judgment.md` **or** `instructions.md`, `doc.yaml`, optional `operations.yaml`
- `.cursor/foundry/catalog/nodes/{NODE_ID}.index.yaml` — regen via `catalog build` when flow changes
- `.cursor/foundry/cli/foundry_cli/` — only if mechanism moves (executor, `render.py`, `context.py`, `constants.py`, `gates.py`)
- `.cursor/foundry/schemas/context-packet.schema.json` — when engine-owned steps/gates need packet shape changes
- `.cursor/rules/node-instructions.mdc` — ownership table row
- `docs/plans/{NODE_ID}-contract-cleanup-plan.md` — plan artifact (mirror shape-present-gate plan structure)
- Tests: `@node.{NODE_ID}` acceptance feature or scenario; unit tests for render/context/executor changes
- `doc build --workspace /Users/lynnfrank/src/foundry --registry ...` → `docs/nodes/{NODE_ID}.md`
- Optional: `doc build` for `.cursor/foundry/fixtures/apps/foundry-test` when node docs are copied into fixture app

## Presentation (`render.py`)

- **User gates with plan:** `## Living plan` — `shape.record.gate`, `execute.start` (reuse artifact_reads / `plan_path` patterns)
- **User gates with presentation:** `## Plan presentation` — `shape.present.gate`
- **Engine-owned intake:** `## Intake` / `## Execute intake` — `shape.intake`, `execute.intake`
- **Engine intake gate:** `## Intake evidence` — `execute.intake.gate`

Keep steward prompts out of duplicated prose; point at markdown packet sections.

## Engine-owned steps (`constants.py`)

`ENGINE_OWNED_STEP_NODE_IDS` must include every step with **no** judgment file on the happy path. Context assembly must not require `instructions` / `instructions_path` (extend `context-packet.schema.json` `enum` exemption list with `shape.intake` pattern).

## Judgment + complete operations (shape execute pattern)

Examples: `shape.present` → `visit.present.complete`; `shape.record` → `visit.record.complete`.

- Task YAML + JSON result schema
- Executor applies state, publishes artifacts, seals receipt, transitions
- Remove `allow.files.write`, `allow.state` broad grants, and legacy `worker:` from flow when task replaces worker
- `advance.py`: agent wait on boundary, not host-only auto-complete for judgment steps

## Gates — do not

- Add `allow.cli` for `gate decide` on user gates (engine-global)
- Use `visit transition` on gates (`GATE_USE_DECIDE` policy)
- Bind a model worker to summarize gate content

## Engine gates — do

- Document `run advance` in `instructions.md`
- Expose `decider: engine` on context packet when useful for stewards
- Map sealed upstream receipts in `gates.py` / context reads when stewards need evidence

## Testing

```bash
cd /Users/lynnfrank/src/foundry/.cursor/foundry/cli
.venv/bin/python -m pytest <targeted paths> -q
.venv/bin/python foundry.py --json doc build --workspace /Users/lynnfrank/src/foundry --registry /Users/lynnfrank/src/foundry/.cursor/foundry
```

- Prefer existing slice features (`execute_slice_2a`, `shape_phase_e2e`, `run_context.feature`)
- Add fixture under `.cursor/foundry/fixtures/runs/` when a gate needs an opened-at-node scenario

## Commit hygiene (verifier — orchestrator runs this)

**Exclude from commits:** `docs/nodes/cli/`, `docs/nodes/nodes/`, bulk `.cursor/foundry/cli/docs/*` from wrong output dir, unrelated `docs/index.md` churn.

**Include:** plan file, flow, registry nodes, catalog index, tests, `docs/nodes/{NODE_ID}.md`, `node-instructions.mdc`, `node-inventory.md` if stale.

## Reference plans (by archetype)

| Archetype | Plan |
|-----------|------|
| User gate | [shape-present-gate-contract-cleanup-plan.md](shape-present-gate-contract-cleanup-plan.md) |
| Judgment step | [shape.record-contract-cleanup-plan.md](shape.record-contract-cleanup-plan.md) |
| Engine-owned step | [execute.intake-contract-cleanup-plan.md](execute.intake-contract-cleanup-plan.md) |
| Engine gate | [execute.intake.gate-contract-cleanup-plan.md](execute.intake.gate-contract-cleanup-plan.md) |
| User gate + living plan | [execute.start-contract-cleanup-plan.md](execute.start-contract-cleanup-plan.md) |

## Completed nodes (do not re-scope)

`shape.intake` through `execute.intake.gate` — see [workflow-node-revision-orchestration.md](workflow-node-revision-orchestration.md).
