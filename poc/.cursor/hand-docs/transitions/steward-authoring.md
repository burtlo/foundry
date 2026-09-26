# Steward authoring — commands and step instructions

Status: **authoring rules** for humans and agents writing `/craft-*` slash commands and `.cursor/foundry/nodes/{node-id}/instructions.md` steward instructions.

**Related:** [README.md](README.md) (POC port, worker prompts), [command-bodied-checks.md](command-bodied-checks.md) (engine checks), [capabilities.md](../workflow-schema-v1/capabilities.md) (reads / allow).

---

## Approach

Foundry v1 splits **engine** behavior from **steward** behavior.

| Actor | Role |
| --- | --- |
| **Engine** | Admit visits, run lifecycle hooks and catalog checks, assemble context packets, route after seal |
| **Steward** | Conversation, allowed state/files, worker launch, evidence assembly, `allow.cli` calls |
| **Worker** | Assessment or build task; returns structured output; does not route or seal |

Steward-facing text is **traffic at one node**, not a marathon orchestrator. The engine already decided eligibility before returning a context packet.

### Three layers (do not collapse)

| Layer | Path | Loaded when | Ends where |
| --- | --- | --- | --- |
| Product command | `.cursor/commands/craft-*.md` | User invokes `/craft-*` (once per chat) | Context packet loaded; defer to `instructions_path` |
| Step instructions | `.cursor/foundry/nodes/{node-id}/instructions.md` | `run context` resolves `instructions_path` | `transition` requested (close only) |
| Node reference | [docs/generated/nodes/{node-id}.md](../generated/nodes/) | **Authors and humans only** — not runtime steward load |

**Handoff rule:** the product command stops where the step file starts. Never duplicate step content inside a command.

### Context pressure (shape phase)

Shape is **one chat** across multiple nodes (`shape.intake` → `shape.examine` → …). To limit token load and conflicts:

| Load once per chat | Load per active visit only |
| --- | --- |
| `/craft-*` bootstrap + defer | Step file from current `instructions_path` |
| | Context packet (`reads`, `allow`, `worker`) |

After each `transition`, run `run context` again and follow the **new** `instructions_path` only. Do not re-expand the product command or prior step files in prose.

### The one-question test

Before adding a line to a command or step file, ask:

> Would the engine already have done this before returning my context packet?

If **yes** → delete it from steward-facing text. Put it in generated node docs (`foundry dev docs`) or CLI specs instead.

---

## Engine domain (negative space)

Do **not** put these in `/craft-*` commands or `nodes/*/instructions.md`:

| Topic | Why it is engine-owned |
|---|---|
| Lifecycle states (`examined`, `opened`, `closed`, `sealed`) | Engine transitions; steward acts only while `opened`, which is implicit once context loads |
| Hook names and timing (`on_examine`, `on_open`, `on_close`, `on_seal`) | Engine runs before steward work opens |
| Catalog check probes (`validate-manifest`, `intake-receipt-sealed`, …) | Engine records `check.recorded`; steward does not re-run probes |
| Verifying `lifecycle` or `node_id` after `run context` | Context packet is proof of position; redundant self-checks add noise |
| Connection selection and next node | Routing happens after seal; steward does not pick destinations |
| `recommended_next_state`, next-node ids (`shape.examine`, …) | Receipt routing fields and destinations are engine-owned after seal |
| Admission source (`entry`, loops) | Engine admits; product command may call `run create` for entry only |
| Reshape / loop branches | Removed from v1 flow; do not author loop-specific steward branches |
| Links to `factory-flow.yaml`, `docs/generated/nodes/*.md` | Authors only; stewards use the context packet |

Steward **may** read ledger events when **assembling evidence** (e.g. intake receipt `checks[]` at seal time). That is not the same as inspecting lifecycle or re-running hooks.

---

## Steward domain

### Step instructions may include

| Concern | Detail |
|---|---|
| Goal | One sentence: what this visit produces (no routing target) |
| User conversation | Confirm work request, ask within `allow.user` |
| State | `visit state patch` for paths in `allow.state` |
| Files | Write paths from resolved `allow.files.write` grants in the packet |
| Worker launch | Bind from context `worker`; pass resolved inputs only |
| Evidence | Merge worker output; build receipt JSON; seal via `receipt.link` |
| Publish | `artifact.publish` for declared artifacts |
| Close | `visit transition` — requests close only |
| Boundaries | Short list of node-specific prohibitions |

### Ticket ownership (`shape.intake` pattern)

| Owner | Responsibility |
|---|---|
| **Worker** | Propose ticket fields (`raw_input`, `normalized_translation`, `source_type`, `source_ref`, …) and assessment |
| **Steward** | Launch worker with `work_prompt`; write `ticket.json` **once** from worker output; publish artifact |

Do not have the steward draft ticket fields and then re-draft from the worker unless the user edits mid-visit.

### Commands may include

| Concern | Detail |
|---|---|
| User input | `work_prompt` — capture verbatim only; no fetching |
| Bootstrap | `cli resolve` (pre-run), then `run create` or `run resume`, then `run context` |
| Defer | Follow `instructions_path`; pass `work_prompt` when the step says to |
| Bootstrap failure | Manifest/bootstrap failure → `/craft-init` (no catalog check ids) |
| Sibling commands | Short out-of-scope table |

Commands do **not** include application-repo paths, `foundry_cli` paths, `--workspace` prose, or ticket metadata.

---

## Foundry CLI fences (`foundry-invoke`)

Use **`foundry-invoke`** code fences for every Foundry engine call. These are **not** shell commands.

| Fence | Content |
|---|---|
| `foundry-invoke` | Argv tail only — one line, no `python`, no `foundry.py`, no `foundry.sh` path inside the fence |
| `text` / `bash` | Real shell only (`git`, `dotnet`, `gh`) |

The **host** prepends `foundry_cli` from the latest bootstrap or context JSON before each `foundry-invoke` fence. Authors do not instruct stewards to record, prepend, or pass `--workspace` — that is invocation plumbing, not steward work.

### Placeholders (after context loads)

Use names that match the **context packet**, not ad hoc prose:

| Placeholder | Source |
|---|---|
| `{run_id}` | packet `run_id` |
| `{visit_id}` | packet `visit_id` |
| `{workspace}` | application repo root (packet `reads.config.workspace` or bootstrap JSON) |

Do **not** hardcode `.cursor/foundry/cli/foundry.sh` or `.cursor/foundry/cli/foundry.py` in commands or steps — that breaks when Foundry is an installed plugin separate from the app repo.

### Example

```foundry-invoke
run context --run "{run_id}" --json
```

```foundry-invoke
visit state patch --run "{run_id}" --set '{"app_folder": "<resolved path>"}' --json
```

---

## Writing `/craft-*` commands

### Required shape

```markdown
---
name: craft-<phase>
description: >-
  Third-person: what it does and when to use it (trigger terms).
---

# Craft <phase>

[Role: one line]

## User input

[work_prompt capture only]

## Bootstrap

[cli resolve → run create/resume → run context → defer to instructions_path]

## Out of scope

[sibling /craft-* table]
```

### Rules

1. **Bootstrap only** — `cli resolve`, then `run create` (or `run resume`), then `run context`, then stop instructing.
2. **No environment or invoke prose** — no `**Application repo:**`, no `**Foundry CLI:**` path lines, no "Record `foundry_cli` / `workspace` from the response" between fences; the host handles invocation from bootstrap JSON.
3. **No step duplication** — defer to `instructions_path`.
4. **No lifecycle checks**, **no next-node prep**, **no node doc links**.
5. **Work prompt is opaque** — capture verbatim only. Do not enumerate how the user supplied it (no "paste, file path, URL, …").
6. **Bootstrap failure** — manifest/bootstrap failure → `/craft-init`; do not name catalog check ids.
7. **Bootstrap is fences only** — consecutive `foundry-invoke` fences with at most one-line failure handling (`/craft-init`); no setup narration between them.

### Anti-patterns (commands)

| Anti-pattern | Fix |
|---|---|
| `**Application repo:**` / `**Foundry CLI:**` blocks | Delete; use `cli resolve` + packet JSON |
| "Record `foundry_cli`" / "Prepend `foundry_cli`" in Bootstrap | Delete; host handles invocation |
| Enumerating work-prompt source kinds | "Capture verbatim" only |
| Hardcoded `.cursor/foundry/cli/...` paths | `foundry-invoke` + `foundry_cli` from JSON |
| ` ```text ` fences for `run create` | `foundry-invoke` fences |
| Phase duplicating step file | Defer to `instructions_path` |
| Ticket / `source_type` in command | Step file only |

---

## Writing `nodes/{node-id}/instructions.md`

### Required shape

```markdown
# <Title>

## Goal

[Single outcome — no routing target]

## While opened

[Ordered steps; foundry-invoke fences for CLI]

## Boundaries

[3–5 bullets — prohibitions only; no catalog check ids]
```

No header line linking to `factory-flow.yaml` — the context packet is the runtime contract.

**Boundaries** list node-specific prohibitions in plain language. Do not name catalog check ids (`validate-manifest`, …) — say "do not re-run manifest validation" instead.

### Rules

1. **Length budget** — ≤ 80 lines total (context pressure). Prefer schema references over inline field recipes.
2. **Assume context is loaded** — no `run context` in the step file.
3. **No routing targets** — Goal and body describe artifacts/evidence only; no next-node ids, no `recommended_next_state`, no "prepare for shape.examine".
4. **No engine narration** — no lifecycle, hooks, or registry file links.
5. **`foundry-invoke` only** for Foundry CLI; placeholders from the packet.
6. **`ledger show` flags** — only flags documented in [cli-ledger.md](../cli-v1/cli-ledger.md) (`--run`, `--from-seq`, `--to-seq`, `--types`, `--json`). Filter events to this `visit_id` during assembly — do not use undocumented flags such as `--visit`.
7. **Worker inputs explicit** — table of Task launch fields.
8. **Evidence order** — worker → `ledger show` → assemble receipt drafts → write `ticket.json` from worker → publish → seal receipts → `transition`.
9. **Receipt assembly** — point to schema paths (`registry:schemas/intake-receipt.schema.json`, …); do not inline full field lists, UUID generation, or timestamp format recipes.
10. **Path B intake** — `ledger show` with `--types check.recorded` when assembling receipt `checks[]` for this `visit_id`; do not name hooks; do not pass `checks[]` to the worker.
11. **Every branch gets `foundry-invoke` fences** — blocked and proceed paths each show applicable `receipt seal` / `artifact publish` / `transition` lines.
12. **Registry sync** — same change updates `factory-flow.yaml` (see below).
13. **After transition** — not in the step file; shape chat reloads context for the next node elsewhere (command once, then per-visit steps).

### Anti-patterns (steps)

| Anti-pattern | Fix |
|---|---|
| "Contract in factory-flow.yaml" header | Delete |
| Steward drafts ticket then re-drafts from worker | Worker proposes; steward writes once |
| ` ```text ` / shell fences for foundry argv | `foundry-invoke` |
| Hardcoded foundry bundle paths | `foundry_cli` from packet |
| Hook names in steward text | "ledger `check.recorded` for this visit" |
| `ledger show --visit` or other undocumented flags | Flags from [cli-ledger.md](../cli-v1/cli-ledger.md) only; filter by `visit_id` in assembly |
| `recommended_next_state` / next-node ids in body | Delete; routing is post-seal |
| Inlined receipt JSON field recipes | "Build draft per `registry:schemas/…`" |
| Catalog check ids in Boundaries | Plain-language prohibition |
| Step > 80 lines | Trim recipes; reference schemas |
| Steward CLI without `allow.cli` update | Registry sync |

---

## Registry sync (authoring only)

When you add or change steward CLI in a step file, **update the node** in `.cursor/foundry/flows/factory-flow.yaml` in the **same change**. Authoring-time only — not runtime elevation.

| Step adds… | Update in YAML |
|---|---|
| `visit state patch` | `allow.cli`: `visit.state_patch`; `allow.state`: patched paths |
| `ledger show` | `allow.cli`: `ledger.show` |
| `artifact publish` | `allow.cli`: `artifact.publish`; `produces` + `allow.files.write` |
| `receipt seal` | `allow.cli`: `receipt.link`; `receipts` schemas |
| `visit transition` | `allow.cli`: `transition` |
| Receipt JSON drafts (`run:receipts/...`) | `allow.files.write` for each draft path the step writes before `receipt seal` |
| Ticket or artifact draft paths | `allow.files.write` (and `produces.artifacts` when publishing) |

Do **not** add `allow.cli` for engine hooks (`app validate`, catalog checks) or product bootstrap (`run create`, `run context`, `cli resolve`).

Do **not** change the node's `instructions:` pointer unless you are deliberately binding a different step file.

Capability ids: dot notation (`ledger.show`, `visit.state_patch`, `artifact.publish`, `receipt.link`, `transition`). See [cli.md](../cli-v1/cli.md) § Capability ids.

When `allow.cli` changes, update `docs/cli-v1/acceptance/features/run_context.feature` (or the node's feature) so capability lists stay in sync, then run `pytest tests/acceptance/test_run_context.py`.

---

## Checklist before merge

Use the checklist below and run `foundry dev all` from `.cursor/foundry/cli` before merging steward-facing changes.

### Command

- [ ] `foundry-invoke` fences only (no hardcoded bundle paths)
- [ ] `cli resolve` before first run when no context exists
- [ ] User input section: `work_prompt` only
- [ ] Bootstrap → defer to `instructions_path`; no setup prose between fences
- [ ] No environment prose, step duplication, or lifecycle checks
- [ ] User input does not enumerate source kinds

### Acceptance

- [ ] `foundry dev acceptance` exits 0 (or `pytest tests/acceptance/test_run_context.py`)

### Step

- [ ] ≤ 80 lines; no factory-flow / node-doc links
- [ ] Goal has no routing target; no `recommended_next_state` or next-node ids
- [ ] `foundry-invoke` fences; packet placeholders; `ledger show` flags per cli-ledger.md
- [ ] Receipt drafts reference schemas — no inlined field recipes
- [ ] Worker proposes ticket; steward writes once and publishes
- [ ] Evidence order and branch CLI fences complete
- [ ] Registry sync: `allow.cli` / `allow.state` / `allow.files.write` match step; `instructions:` unchanged unless rebinding step
- [ ] Boundaries: 3–5 bullets; no catalog check ids; no reshape / next-node content

---

## Examples

**Command bootstrap (ends at defer):** User input: `work_prompt` only. Bootstrap: three consecutive `foundry-invoke` fences (`cli resolve`, `run create`, `run context`); on create failure → `/craft-init`; then follow `instructions_path`. No prose between fences.

**Step (no overlap):** Goal names artifacts only. Worker proposes ticket fields; steward assembles receipt drafts per schema paths, writes `ticket.json` once, then publish → seal → `transition`. `ledger show` uses documented flags; filter events to `{visit_id}` during assembly.
