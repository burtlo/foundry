# Workflow node review prompt (generic)

Use this prompt **one node at a time**. Replace `{NODE_ID}` with the target node id (e.g. `shape.examine`, `execute.intake`).

Copy everything below the horizontal rule into a new chat (or attach this file) and fill in the node YAML from `flows/implementation/registry.yaml`.

---

We are reviewing Foundry one workflow node at a time.

For this review, analyze **ONLY**:

`{NODE_ID}`

Do not redesign the entire workflow. Do not proceed to later nodes. Do not create a broad implementation plan for Shape, Execute, or Verify.

The purpose of this exercise is to make each node small, explicit, deterministic where possible, and dependent on model judgment only where model judgment provides real value.

## Architectural principle

Foundry is moving away from nodes that are primarily large sets of agent instructions.

Use this responsibility model:

### Judgment → Model

The model should handle work requiring semantic interpretation, ambiguity resolution, evaluation of meaning, synthesis, or other genuinely nondeterministic reasoning.

### Mechanism → Engine / Tool

Foundry should perform deterministic actions such as:

- reading known state
- writing known state
- publishing artifacts
- storing receipts
- invoking tools
- assembling context
- resolving registry resources
- recording evidence
- advancing workflow state

Do not instruct an agent to perform deterministic bookkeeping that Foundry can perform itself.

### Policy → Engine

Deterministic rules governing whether an operation is allowed, whether prerequisites exist, whether a gate passes, or whether a transition may occur belong in executable policy/checks whenever practical.

Do not rely on an agent remembering a rule that Foundry can enforce.

### Presentation → Client / Renderer

Formatting or presentation behavior that does not affect semantic judgment should not inflate the worker prompt.

## Current node

Paste the **full** node entry from `.cursor/foundry/flows/implementation/registry.yaml` (including `produces`, `instructions`, `operations`, `reads`, `allow`, `receipts`, `lifecycle`, `worker` / `task` bindings if present, and any node-specific fields).

```yaml
# Paste flows/implementation/registry.yaml node block for {NODE_ID} here
```

## Step 1 — Reconstruct what actually happens

Do not rely on the node title or `judgment.md` / `instructions.md` as the definition of the node.

Trace the implementation.

Inspect:

- this schema entry
- `registry:nodes/{NODE_ID}/judgment.md` and/or `registry:nodes/{NODE_ID}/instructions.md` (whichever the flow references)
- `registry:nodes/{NODE_ID}/operations.yaml` (if present)
- checks referenced by lifecycle (`flow.checks` in flows/implementation/registry.yaml)
- CLI commands exposed through `allow.cli`
- dedicated executors in `foundry_cli/engine/` (grep for `{NODE_ID}`)
- `advance.py` / `run_service.py` boundaries and `run.wait` behavior
- state handling
- artifact handling
- receipt generation and validation
- transition and routing (connections from this node)
- tests (acceptance features tagged or naming the node; unit tests)
- feature documents and generated docs under `docs/nodes/{NODE_ID}.md`
- `registry:nodes/{NODE_ID}/doc.yaml` if present
- callers and consumers of the node (incoming connections, `reads.artifacts` on downstream nodes)
- relevant schemas (`produces`, `receipts`, state patches)

Reconstruct the **actual runtime sequence** from entering `{NODE_ID}` until the node is sealed, reopened, halted, or otherwise terminal for that visit.

Show that sequence explicitly (numbered steps or diagram).

Note whether `operations.yaml` is **executed** by the engine or only **loaded for context** (run context / docgen).

## Step 2 — Establish the node's contract

Before recommending changes, answer:

### Inputs

What must already exist when `{NODE_ID}` begins?

Distinguish:

- configuration
- workflow state
- files/artifacts
- runtime metadata
- information requiring semantic interpretation

### Outputs

What must exist when `{NODE_ID}` successfully completes?

Distinguish:

- state
- artifacts
- receipts/evidence
- semantic conclusions

### Success condition

What exactly does successful completion mean?

Do not answer merely "the node sealed."

Describe what Foundry can legitimately assume after this node succeeds.

### Failure conditions

Enumerate meaningful ways this step can fail.

For each, determine whether the failure is:

- deterministic
- semantic/judgment-based
- infrastructure/tooling
- invalid workflow state

### Consumer

Identify exactly which later node or system behavior depends upon each output.

If an output has no consumer, flag it.

## Step 3 — Classify every responsibility

Create a responsibility table.

For every meaningful behavior performed by this node, classify it as:

**JUDGMENT** — Requires model reasoning.

**MECHANISM** — Deterministic operation Foundry should perform.

**POLICY** — Deterministic rule Foundry should enforce.

**PRESENTATION** — Formatting/display concern.

For each responsibility report:

| Responsibility | Current owner | Correct category | Recommended owner | Evidence |
|---|---|---|---|---|

Be aggressive.

Something being implemented in instructions today does NOT mean it belongs to the model.

Something being available as a CLI operation does NOT mean the model should decide when or how to invoke it.

## Step 4 — Audit the schema itself

Review **every** schema field on this node entry.

For each field ask:

1. Why does `{NODE_ID}` need this?
2. What implementation consumes it?
3. Is it required for the node contract?
4. Is it exposing capability the worker should not need?
5. Is it redundant with lifecycle/engine behavior?
6. Is the permission narrower than necessary, broader than necessary, or correct?

Review individually (as applicable to this node):

- `kind`, `title`, `terminal`, `decider`, `worker`, `task` bindings
- `produces` (artifacts, options for gates)
- `instructions` / judgment vs instructions split
- `operations`
- `reads` (config, state, artifacts, user)
- `allow` (state, files, cli, user)
- every `allow.files.write` entry
- every `allow.cli` entry
- `receipts`
- every `lifecycle.on_examine` / `on_open` / `on_close` / `on_seal` check
- every `on_fail` behavior

Do not preserve fields simply because the schema supports them.

The desired node is the **smallest correct contract**.

## Step 5 — Audit instruction prose aggressively

This is the most important part of the review.

Go through the active instruction file (`judgment.md` or `instructions.md`) **instruction by instruction**.

For every instruction classify it:

**KEEP** — Genuine model judgment required by this node.

**ENGINE** — Foundry should perform this deterministically.

**POLICY** — Foundry should enforce this deterministically.

**SCHEMA/CONTRACT** — Belongs in schema, operation definition, structured I/O, or validation rule rather than prose.

**REDUNDANT** — Worker already knows this from constrained context or operation contract.

**DELETE** — Serves no remaining purpose.

For every **KEEP** instruction, explain why an LLM is actually necessary.

The burden of proof is on keeping prose.

Do not improve verbose instructions that should instead disappear.

If a bound subagent exists (`.cursor/agents/…`), note whether it is on the happy path or legacy/unbound.

## Step 6 — Question whether an agent is needed at all

Explicitly answer:

> Does `{NODE_ID}` require a model worker?

Consider three possibilities:

### A. Fully deterministic node

Everything can be performed through schema validation, checks, state operations, and engine logic.

No agent should run.

### B. Deterministic node with one bounded judgment operation

Most work is mechanical, but one specific question requires semantic judgment.

If so, define that judgment as narrowly as possible:

**Input → Judgment question → Structured output**

The worker should not need to understand or operate the rest of the lifecycle.

### C. Judgment-heavy node

A worker genuinely needs substantial context and discretion.

Choose this only if the implementation demonstrates why.

Do not assume every existing node needs an agent because historically every node had instructions.

## Step 7 — Look for duplicated ways of doing the same thing

Pay particular attention to cases where the schema appears to expose both:

- a low-level mechanism
- and a higher-level operation accomplishing the same lifecycle action.

Investigate relationships among capabilities such as (as applicable):

- `transition` vs node-specific `visit.*.complete` commands
- `visit.state_patch` vs direct state permissions
- direct file writes vs `artifact.publish`
- `receipt.link` / `receipt seal` vs executor-internal sealing
- steward manual path vs `advance_run` auto-completion

Ask whether the node is exposing implementation primitives that should be encapsulated behind one semantic operation.

Prefer:

`complete {phase}` (one command)

over requiring a worker to understand:

`write file → publish artifact → patch state → link receipt → transition`

when those steps are deterministic consequences of success.

## Step 8 — Identify hidden orchestration in prose

Search for instructions equivalent to:

- first do X, then call Y
- write Z, update state, record a receipt
- transition when finished
- retry if…, don't continue until…
- make sure file X exists

These belong in operations, lifecycle, checks, or engine code.

The model should preferably receive a **question to answer**, not a miniature workflow to execute.

## Step 9 — Propose the minimal node

After the analysis, propose what `{NODE_ID}` should look like if designed according to these principles.

Provide:

### Minimal schema

Show a proposed YAML definition for this node only.

Remove unnecessary capabilities.

Do not add speculative framework features.

### Minimal judgment contract

If a model is still required, show the conceptual contents of the resulting instruction file (aim for the smallest useful prompt).

If no model is required, say so and where steward/product guidance should live instead (e.g. craft command only).

### Deterministic responsibilities

List exactly what Foundry should perform before and after any judgment operation.

Target shape:

**Engine prepares → model judges only if necessary → engine validates/records/transitions**

not:

**Engine starts agent → agent operates Foundry correctly**

## Step 10 — Compare current vs proposed

Finish with:

### Current

How much responsibility does the node currently place on its worker/steward?

### Proposed

How much remains after moving deterministic behavior into Foundry?

### Removed from agent responsibility

Enumerate everything the model no longer needs to know or do.

### Remaining judgment

Enumerate the exact semantic questions that still require a model (if any).

### Implementation changes

List the **smallest concrete changes** necessary to move from current to proposed.

Do **NOT** implement them in this review unless explicitly asked.

## Stop condition

Stop after `{NODE_ID}`.

Do not analyze sibling nodes or the whole phase.

Do not review the next node in the graph.

Do not produce a roadmap for the entire workflow.

We are deliberately establishing the architecture one node at a time.

The result of this review becomes the reference pattern for the next node.

## Optional: node checklist (quick grep)

Before or during the review, the reviewer may run:

- `rg '{NODE_ID}' .cursor/foundry .cursor/foundry/cli docs`
- Read `docs/nodes/{NODE_ID}.md` if generated
- Read `.cursor/foundry/catalog/nodes/{NODE_ID}.index.yaml` if present

---

## Usage example

1. Open `flows/implementation/registry.yaml`, copy the node block for `shape.examine`.
2. Replace `{NODE_ID}` with `shape.examine` throughout this prompt.
3. Paste the YAML into the "Current node" section.
4. Run the review in a dedicated chat; save conclusions in a per-node note if desired (e.g. `docs/plans/node-reviews/shape.examine.md`).
