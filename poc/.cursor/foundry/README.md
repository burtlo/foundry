# Software Factory (Foundry)

Foundry is the **stateful planning and execution system** for feature work. Entry skill: `.cursor/skills/foundry/SKILL.md`. CLI: `.cursor/foundry/cli/foundry.py`. Team config: `.cursor/foundry/profiles/*.yaml`.

Intake sources (`intake.source`): `jira` · `local` · `chat`. Local markdown tickets: [`docs/local-tickets.md`](docs/local-tickets.md).
New applications create `.foundry/app.yaml` through
[`foundry-app-bootstrap`](../skills/foundry-app-bootstrap/SKILL.md).

## Directory layout

```text
.cursor/foundry/
  README.md           # this file
  schemas/            # JSON Schema contracts (draft 2020-12)
  profiles/           # validated, standalone team profiles
  flows/
    factory-flow.yaml           # step order, gates, skip rules — the source of truth
    factory-flow.generated.mmd  # generated; CI fails when stale
  steps/              # one .md per dotted step ID
  cli/
    foundry.py        # state engine CLI
    requirements.txt
    tests/
  knowledge/          # promoted repo knowledge (Phase 7)
  runs/               # placeholder; live runs live in {app}/.foundry/runs/
```

**Per-run artifacts** (gitignored) live next to the app being edited:

```text
{app_folder}/.foundry/runs/{run_id}/
  state.json
  app-manifest.json    # immutable canonical snapshot of .foundry/app.yaml
  config.json
  ticket.json          # sealed intake (local file or paste)
  events.jsonl
  staging/{launch_id}.json|.meta.json|.craft.json
  receipts/{receipt_id}.json   # engine-written only
  execution-graph.json
  brief.md
  handoff.md / handoff.json
  learning_record.json / learning_review.md
  status.md            # generated human summary (Swamp Club / standup)
```

`factory_root` in run state still points at this repo (`github-private`) for config and schemas.
`config.json` is the immutable resolved profile used by the run; `state.json`
stores its SHA-256 as `resolved_profile_hash`.

### Run context (orchestrator)

The parent agent never hardcodes `python .../foundry.py` inside step units. The CLI emits a copy-pasteable invocation prefix, per-run paths, and a `steward_allowlist`:

| Field | When available |
|-------|----------------|
| `foundry_cli` | `cli resolve`, `run init`, `run context`, `flow orchestrator-packet` |
| `state_path`, `config_path`, `run_dir`, `app_folder`, `factory_root` | Same commands (after `run init`) |
| `steward_allowlist` | `flow orchestrator-packet` / `flow resume-packet` (argv prefixes + path roles) |
| `session_stop_hint` | Same — handoff after worker/hard gate |
| `next_commands` | `flow orchestrator-packet` (full commands, including `foundry_cli` prefix) |

Integrity: `run integrity-check --state …` (required before handoff when `foundry.orchestrator.require_integrity_check` is true). Thresholds: `eval/thresholds.yaml` (`integrity:` + packet `*_max` flags) via `metrics check-thresholds`. Schemas: `schemas/packets/ticket.schema.json`, `schemas/packets/agent-craft.schema.json`.

Pre-run bootstrap:

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" cli resolve --factory-root "{factory_root}"
```

Bootstrap with `python` on PATH once; `foundry_cli` in the JSON is shell-safe (`foundry.ps1` on Windows, `foundry.sh` elsewhere). Copy it verbatim; do not hand-build interpreter paths.

Step units and `.cursor/skills/foundry/SKILL.md` use **`foundry-invoke` fences** (argv tail only). The parent prepends `foundry_cli` from the latest JSON response. Validate with `docs validate-invokes` (also runs during `flow validate`).

## Jobs, not marathons

Foundry is designed for **multi-chat stewards**, not one agent holding the whole pipeline.

| Intent | CLI entry |
|--------|-----------|
| new | `run init [--interaction-mode …]` |
| resume | `run latest` → `flow resume-packet` |
| administer | after graph; drive `worker next-builder` |
| ship | `deliver.*` when delivery-check passes |

**Interaction modes** (frozen at init; IoT default `drive_to_pr`):

- `interactive` — human gates as in the registry
- `drive_to_pr` — auto rubber-stamp eligible gates; hard stops at AC freeze and ready-for-PR (code review / pre-PR)
- `plan_control` — like drive_to_pr but brief + graph stay human

Record the host-provided conversation ID with `cursor session-record` after
run creation or resume. After a hard gate or build verify, write `run handoff`
(`handoff.md` + `handoff.json`) and open a **new** Agent chat with the kickoff
prompt. A different host ID proves freshness; if no source ID was recorded,
the first non-empty post-handoff host ID clears the obligation as recovery
without claiming identity proof. Seam contracts:
[`docs/seam-packet-catalog.md`](docs/seam-packet-catalog.md). Worker craft vs
Foundry telemetry: [`docs/worker-launch-contract.md`](docs/worker-launch-contract.md).
Post-run offline learning: [`docs/post-run-learning.md`](docs/post-run-learning.md)
(`run finalize-learning` / `run complete`), followed by optional authenticated
`outcome observe` to append PR checks and merge state.

**Token rule:** load resume-packet + one step unit only — never full events or all receipts.

## Schemas

Runtime protocol artifacts use `schema_version: 2.2.0` and reject earlier run
state, events, graphs, receipts, craft, resume, launch, and handoff packets.
The 2.1 contract adds transactional revisions, evidence lineage, packet
utilization, and capability ownership. Profiles and sealed tickets retain
independent `1.0.0` formats.

### `app-manifest.schema.json`

The application-owned `.foundry/app.yaml` contract uses integer
`schema_version: 1`, independent of the runtime protocol version. Fixtures live
under `schemas/fixtures/`; `foundry_app.py` validates and canonicalizes the
authoring manifest, and run init freezes it as `app-manifest.json`. The `2.2.0`
runtime cutover is documented in
[`docs/protocol-2.2-cutover.md`](docs/protocol-2.2-cutover.md).
Factory CI validates the schema corpus and IoT reference manifest on Windows
and Linux. App manifests are validated during bootstrap; app-repository CI is
outside the factory-only validation contract.

### `factory-run-state.schema.json`

Durable per-run state updated by atomic compare-and-swap replacement. Tracks a
monotonic `state_revision`, transaction ID, current step, ticket context,
approved acceptance criteria, evidence digests, and receipt references.

### `factory-event.schema.json`

Append-only audit log entries (one JSON object per line in `events.jsonl`). Records who did what and when: state transitions, gate presentations/resolutions, subagent launches, CLI invocations, blocks, and failure classification. Payload shape varies by `event_type`.

### `agent-receipt.schema.json`

Structured output from one subagent invocation. Captures agent name/mode, status, exploration trace (searches, files examined, hypotheses), decisions, outputs, commands run, validation counts, blockers, and `recommended_next_state` for the engine to consume.

### `execution-graph.schema.json`

Planner output decomposing ticket work into `work_items` (id, owner, dependencies, AC refs, evidence requirements) plus a `verification_plan` (validator, bugbot, security-review ordering). Approved at `plan.graph` before builders start.

### `factory-flow.schema.json`

Validates `factory-flow.yaml` structure: flow definitions (entry, steps, edges), gate definitions, and references to step unit markdown files. YAML is parsed to JSON before validation.

### `factory-config.schema.json`

Validates standalone team profiles. `profiles/default.yaml` is the shipped
default and `profiles/example-team.yaml` proves a second team can use the
same contract.

## Flow registry

`flows/factory-flow.yaml` defines the `implementation` and `analysis` flows over 24 step units. `foundry.py` reads it for every decision; nothing in the CLI hardcodes the pipeline.

**Expression language** used by `when` (edges), `when_skip` (steps), `requires` (steps), and `gate.require`:

| Feature | Syntax |
|---------|--------|
| Namespaces | `config.*`, `state.*`, `decision` |
| Operators | `!` `&&` `\|\|` `==` `!=` `<` `<=` `>` `>=` `(` `)` |
| Literals | `true` `false` `null` `'text'` `123` |
| Keyword | `always` (bare `when` only) |

Dotted lookups match the longest existing key first, so `state.steps.implement.code_review.approved` resolves the literal `steps["implement.code_review"]` map rather than descending through `implement`.

**Enforcement points**, in the order `transition` applies them:

1. An edge from the current step to the target must exist and its `when` must hold.
2. The gate on the step being left must be satisfied — unless the edge is `rework: true`.
3. The target's `requires` expressions must hold, judged after the source step is closed out.
4. When the target sets `require_delivery_check: true` (`deliver.scope_comment`, `deliver.ship`), `delivery-check` must pass.

Nothing is written to `state.json` until all four pass.

**Step units** carry frontmatter (`step_id`, `title`, `subagent`, `run_modes`, `delivery_gate`, `state_keys`). `flow validate` fails when a unit disagrees with the registry, so the two cannot drift.

## CLI commands

| Command | Behavior |
|---------|----------|
| `run init --app-folder --issue-key --run-mode [--interaction-mode]` | Create `state.json`, `events.jsonl`, and `receipts/` |
| `run list --app-folder` | Open (incomplete) runs |
| `run latest --app-folder [--issue-key]` | Newest open run |
| `run handoff --state` | Write `handoff.md` / `handoff.json` for the next chat |
| `run finalize-learning --state` | Offline `learning_record.json` + review markdown |
| `run abandon --state --reason` | Mark abandoned + finalize learning |
| `run recover --state` | Remove abandoned temp files and report state/event transaction alignment |
| `run show --state` (or `--app-folder --run-id`) | Current step plus per-step evidence summary |
| `config get --factory-root --role [--app-folder] [--profile]` | Validate and resolve a profile, then emit one of the documented role slices |
| `issue-key parse`, `pr-title`, `git default-branch`, `git staged-secrets-check`, `branch create`, `branch-name` | Shared git / issue mechanics |
| `ticket list\|load\|pick` | Local markdown ticket intake |
| `deliver draft-scope-comment --state` | Markdown scope-comment draft from `pr_extras_register` |
| `deliver pr-verify --state --pr-url --pr-title` | Authenticated `gh` lookup; bind authoritative PR head/title/tree to the delivery seal |
| `jira format-comment --state` | MCP payload for `addCommentToJiraIssue` (only at `deliver.scope_comment`) |
| `run complete --state --pr-url` | Require engine-owned PR verification, record PR URL, complete `deliver.ship`, emit `run_completed` |
| `outcome observe --state [--pr-url]` | Use authenticated `gh` to append an idempotent PR outcome snapshot |
| `external-operation prepare\|record\|reconcile` | Durable idempotency contract for Jira/Confluence/GitHub writes |
| `app discover --app-folder` | Read-only command, routing, tag, and documentation candidates with evidence |
| `app init --app-folder --manifest-file --run-mode [--dry-run] [--force]` | Validate input and deterministically write `.foundry/app.yaml` |
| `app validate --app-folder --run-mode` | Validate app schema, platform commands, capabilities, and builder owners |
| `app print-context --app-folder --run-mode` | Print the resolved canonical manifest, identity, and SHA-256 |
| `project-context --state` | Snapshot-bound commands, verification policy, tags, and documentation context |
| `build --state` / `test --state` | Execute the named canonical snapshot command without shell interpretation |
| `flow current --state` | Active step unit path, subagent, owned state keys, gate prompt |
| `flow next --state --config --decision` | Next step from edges, `when`, `when_skip`, and evidence |
| `flow orchestrator-packet --state` | Thin steward packet + gate_policy / session_stop_hint |
| `flow resume-packet --state` | Step-scoped resume inputs (catalog contract) |
| `gate resolve --state --decision --source human\|auto` | Record gate decision with `gate_source` |
| `flow next --state --config --decision` | Next step from edges, `when`, `when_skip`, and evidence |
| `flow validate` | Schema, unit existence, frontmatter agreement, expressions, orphans, terminals |
| `flow diagram [--check]` | Emit or verify `factory-flow.generated.mmd` |
| `transition --state --to --evidence --set --decision` | Record evidence, enforce the rules above, append events |
| `delivery-check --state --config` | Delivery evidence matrix on dotted step IDs |
| `schema validate --file --schema` | JSON Schema validation |
| `graph validate --file [--state] [--approved-ac]` | Schema + DAG, AC coverage, verification ordering; with `--state`, snapshot builder routing |
| `graph ready --file [--completed <id>]` | Next work items whose dependencies are satisfied |
| `graph record-change --file [--after-build-started]` | Update `plan_stability` on graph edits |
| `build --state` | Run the snapshot's `build` command; returns `receipt_command` for receipts |
| `test --state` | Run the snapshot's `test` command; returns `receipt_command` for receipts |
| `worker builder-packet --state --graph --work-item` | Minimal builder launch packet for one graph node |
| `worker validator-ready --file` | True only when every work item is `completed` |
| `worker validator-packet --state --graph` | Validator inputs: full graph + builder receipt summaries |
| `worker route-critical --graph --findings` | Map critical findings to graph `owner` |
| `worker complete-item --file --work-item --receipt` | Mark a work item completed on the graph |
| `worker rework --state --counter` | Increment `state.rework` counters; block when threshold exceeded |
| `docs pipeline --state [--since]` | Backend-resolved documentation pipeline from snapshot `documentation.model` |
| `docs discover --app-folder` | IoT backend helper: solution structure and AGENTS.md entry-point discovery |
| `docs audit --app-folder` | IoT backend helper: AGENTS.md metadata completeness audit |
| `prd generate --app-folder [--since <commit>]` | IoT backend helper: deterministic PRD compile from AGENTS.md (narrow diffs only) |
| `prd validate --app-folder` | IoT backend helper: 40-point AGENTS.md ↔ PRD validation |
| `prd-sync validate --repo --factory-root` | Publication validator when `publication.required` (IoT PRD sync) |
| `knowledge suggest --receipt [--factory-root]` | Propose gotcha/pattern/convention files (human promotion only) |
| `status --state` (or `--app-folder --run-id`) | Current step, blockers, last 5 events |
| `observability status-markdown --state` | Generate `status.md` for standup visibility |
| `observability receipt show --id --state` | Formatted durable receipt (no transcripts) |
| `observability events tail --state -n 20` | Recent audit events |
| `observability metrics summarize --state` | Rework, gate utility, CLI adoption, eval signals |
| `observability metrics export --state [--output]` | JSON metrics for eval compare-runs |
| `metrics classify --state --failure-class` | Record `failure_classified` event (codes A–I or enum) |
| `metrics suggest --state` | Receipt/event hints for failure taxonomy |
| `metrics compare-runs --baseline --candidate` | Delta report for eval metric exports |
| `metrics check-thresholds --candidate --packet iris-eval-001` | Pass/fail against frozen success thresholds |
| `schema validate-examples` | Validate all JSON fixtures under `schemas/examples/` |
| `worker launch-packet --state` | Atomically records a launch and emits the bounded config, inputs, allowed writes, contracts, craft path, and exact Task prompt |
| `observability subagent complete --state` | Accepts only the launch's craft path; engine binds identity/provenance, validates owned state patches, and writes the durable receipt |
| `observability gate present --state` | Emit `gate_presented` before a human gate resolves |
| `observability receipt validate --receipt` | Durable + semantic receipt validation |
| `plan record-brief --state --brief-file` | Snapshot approved brief hash into run state |
| `cursor session-record --state --conversation-id` | Write `cursor-session.json` for usage enrichment |
| `cursor usage-enrich --state` | Pull Cursor Admin API usage into `cursor-usage.json` |

Transcript lint for eval: `evaluation/scripts/analyze-transcript.py` with `transcript-rules.yaml`.

## Example fixtures

| Fixture | Schema |
|---------|--------|
| `schemas/examples/run-state-implementation.example.json` | `factory-run-state.schema.json` |
| `schemas/examples/execution-graph-iris.example.json` | `execution-graph.schema.json` |

## Validation

Factory-only app-manifest checks: [`docs/app-manifest-validation.md`](docs/app-manifest-validation.md). New apps: [`foundry-app-bootstrap`](../skills/foundry-app-bootstrap/SKILL.md).

```bash
cd .cursor/foundry/cli
pip install -r requirements.txt
python -m unittest discover -s tests -v
python foundry.py flow validate
python foundry.py schema validate-examples
python foundry.py flow diagram --check
```

The `Foundry Flow Check` workflow runs all three on any PR touching `.cursor/foundry/**`.

## Implementation status

| Phase | Status |
|-------|--------|
| 1 — Schemas and layout | Done |
| 2 — State engine and flow registry | Done |
| 3 — Config and team profiles | Done |
| 4 — Intake and grilling | Done |
| 5 — Research, planning, execution graph | Done |
| 6 — Worker runtime and build | Done |
| 7 — Documentation, knowledge, and PRD | Done |
| 8 — Pre-PR gates and review | Done |
| 9 — Delivery and external writes | Done |
| 10 — Observability, receipts, and metrics | Done |
| 11 — Eval harness and quality gates | Done |
| 12+ | See `lynn-notes/foundry/` program plans |

**Deferred out of Phase 2:** `document.*` sub-steps under `implement.documentation` (the documentation-writer runs the full workflow internally) and the `bug_squash` flow.

**Phase 4 (intake):** `intake.refine` → optional `intake.grill` → `intake.present_ac` → `intake.approve_ac`. Grilling skill at `.cursor/skills/grilling/SKILL.md`. CLI: `risk-tier suggest`, `jira format-board`, `intake validate-ac`.

**Phase 5 (planning):** `plan.research` → `plan.brief` → `plan.graph` (skipped when `risk_tier == low`). CLI: `graph validate`, `graph ready`, `graph record-change`. Planner subagent at `.cursor/agents/planner.md`.

**Phase 6 (worker runtime):** Dispatch builders per execution-graph node with `worker builder-packet`; run `build`/`test` via CLI; loop validator with `worker validator-ready` / `route-critical`. Rework counters in `state.rework`. `build-step verify` writes the implement.build step receipt (exit code `0` is success). Transition to `implement.validate` requires that CLI receipt plus a matching `cli_invoked` event. `run block` / `run unblock` stop the parent from advancing while tooling is broken. `graph add-repair-item` appends a `repairer` work item. `flow orchestrator-packet` is the thin parent context when `foundry.orchestrator.thin_context` is true; it includes centralized run context (`foundry_cli`, paths) and fully prefixed `next_commands`.

**Phase 7 (documentation):** Parent runs `docs pipeline --state --since`, then `documentation-writer`, then `knowledge suggest`. Publication (`prd-sync validate`) runs only when pipeline/result `publication.required` is true (`DOCUMENTATION_PUBLICATION`; IoT alias `SYNC_PRD`). Registered models: `iot-agents-prd` (AGENTS.md + PRD) and `feature-records` (Porcelain and other `docs/features` apps). Parent does not run `docs discover` / `docs audit` / `prd generate` / `prd validate`. `implement.documentation` requires `implement.pre_pr_review.human_approved` when `config.review.run_before_pr` is enabled.

**Phase 8 (pre-PR gates):** DevOps workflow scan/pin via `devops scan`, `devops pin-report`, and `devops apply-pin`. Pre-PR critic context via `review bundle`; critic selection via `review critics`; receipt evidence via `review validate-receipts`. `implement.pre_pr_review.human_approved` blocks documentation when review is enabled. DevOps step is skippable via config and recorded as `skipped`. Fix loops from pre-PR review increment `rework.builder_to_bugbot_loops` with configurable threshold and `failure_classified` blocking.

**Delivery:** `delivery-check` must pass before `deliver.scope_comment` or `deliver.ship`. Scope-comment draft via `deliver draft-scope-comment`; Jira MCP payload via `jira format-comment` (only at `deliver.scope_comment`). PR title from `pr-title --state` uses `git.pr_title_pattern` and rejects conventional-commit prefixes. `deliver prepare` binds the staged-secret result, branch, base HEAD, and staged tree before commit. `deliver pr-verify` uses authenticated `gh` lookups to compare the authoritative PR URL, title, head branch, head SHA, commit list, and tree to that seal; only the engine can emit successful verification evidence. After human confirmation, `run complete --pr-url` requires that evidence, rejects tree drift, records `pr_url`, and emits `run_completed`. Analysis runs close from `analysis.deliver` with `run complete` and no PR URL.

**Phase 10 (observability):** Every subagent launch logs `subagent_launched`; completion stores a durable receipt and logs `subagent_completed` / `evidence_recorded`. `status` and `observability status-markdown` work mid-flight. `metrics export` emits compare-runs JSON. Receipts reject telemetry fields (transcripts, model turns). Transcript linter at `evaluation/scripts/analyze-transcript.py`.

**Phase 11 (eval harness):** Failure taxonomy via `metrics classify` / `metrics suggest` (codes A–I). `metrics compare-runs` and `metrics check-thresholds --packet iris-eval-001` compare runs on frozen packets. Metrics exports include `eval_signals` (subagent counts, doc-writer runs, delivery-check bypass from transcript lint, PR/branch violations, gate utility ratio, `build_step_verify_bypass`, `hand_written_receipt_detected`, `parent_app_edit_detected`). Transcript rules also flag `HAND_WRITE_RECEIPT`, `RAW_DOTNET_ORCHESTRATOR`, `CLI_FAILURE_WORKAROUND`, and `PARENT_APP_EDIT`. CI runs `schema validate-examples` plus existing flow/unit/diagram checks. Foundry is the sole orchestrator (`/foundry`); the skill documents the environment banner. Orchestrator fidelity toggles live under `foundry.orchestrator` (IoT profile defaults to strict).
