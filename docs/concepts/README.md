# Foundry workflow concepts

Status: **draft design definition**

This directory defines the target workflow model. It is normative for the meaning of [nodes](graph.md#nodes), [connections](graph.md#connections), [visits](visits-lifecycle.md), [checks](control-plane.md#checks), [policies](control-plane.md#policies), and [actions](control-plane.md#actions). The current `factory-flow.yaml`, JSON Schema, and engine are implementation references until they conform to this definition.

**Product bindings:** the locked v1 product profile is in [`../v1-spec.md`](../v1-spec.md). This hub defines the workflow graph schema; the product spec defines commands, phases, and app-level artifacts.

**Generated documentation:** per-node, worker, flow, and CLI reference pages are produced by `foundry dev docs` from the registry — see [`../index.md`](../index.md). Concepts here explain *why* the registry and engine behave as they do; generated pages show *what* is declared for each node.

**Implementation references:**

| Artifact | Role |
|---|---|
| `.cursor/foundry/flows/factory-flow.yaml` | Authored registry instance |
| `.cursor/foundry/schemas/factory-flow.schema.json` | Structural validation |
| Engine (`foundry.py`) | Execution, semantic validation, ledger |

---

## Charter

Define a workflow as a directed graph whose behavior can be understood from its authored registry and whose execution can be reconstructed from an append-only ledger.

The schema must make these questions answerable:

1. What work or decision does each node own?
2. Which connections may lead into and out of each node?
3. What conditions make a connection eligible?
4. What must be true before a node may start or finish?
5. Who may read, write, decide, or invoke tools while the node is active?
6. Why did a particular run proceed, pause, stop, or choose a connection?

The governing contract is:

```text
Checks evaluate reality.
Policies decide what to do.
Actions control workflow.
Gates make decisions.
Steps produce work.
```

More precisely:

- Checks are observational. They report facts without deciding flow.
- Policies map each check result to one action.
- Actions are the only imperative flow-control mechanism inside a node.
- Connections are the only declarative routing mechanism between nodes.
- A gate records one decision from a closed set of options.
- A step produces declared artifacts.

---

## Normative language

`MUST`, `MUST NOT`, `SHOULD`, and `MAY` are requirements on an authored registry or conforming engine.

Examples omit fields whose defaults are stated in this document. They are illustrative only when explicitly labeled as such.

---

## Conceptual model

```text
Workflow
  ├── entry node id
  ├── check catalog
  ├── nodes[]
  └── connections[]

Node
  ├── identity and kind (step | gate)
  ├── declared output (artifacts | decision options)
  ├── instructions or prompt
  ├── read and capability boundaries
  └── lifecycle hooks

Steward context (per opened visit)
  ├── position, reads, allow, produces, worker paths
  ├── JSON envelope (--json) or markdown packet (--markdown)
  └── inlined step instructions (markdown mode only)

Connection
  ├── identity
  ├── source and target node ids
  ├── seal-outcome selector
  ├── gate-decision selector
  └── optional condition

Run
  ├── mutable state snapshot
  ├── immutable event ledger
  ├── immutable artifact store
  ├── receipt files
  └── visits
```

A **node definition** describes one unit of accountability. A **visit** is one execution of that definition. Routing back to the same node creates a new visit.

A workflow carries one active visit at a time. Connections may form branches, joins, self-loops, and cycles, but they do not create concurrent tokens.

---

## Schema guarantees

This model can describe:

- artifact-producing work nodes;
- stateful decision gates;
- conditional branches;
- decision branches;
- cycles and self-loops;
- cross-node repair loops;
- merge points in a single-token graph;
- pre-work eligibility and prerequisite checks;
- post-work verification and same-visit correction;
- terminal completion;
- auditable pause, halt, skip, and disqualification behavior.

It intentionally defines a single active visit. Therefore, a connection never means fan-out, parallel execution, event subscription, or synchronization. Those meanings MUST NOT be inferred from multiple outgoing or incoming connections.

The model has no subflow call/return construct and no automatic retry action. Same-visit correction uses `reopen`; cross-node rework uses a connection cycle; operator-directed re-evaluation uses escalation resolution `retry`.

---

## Document map

| Document | Contents |
|---|---|
| [README.md](README.md) | Charter, normative language, conceptual model, schema guarantees, reading order |
| [graph.md](graph.md) | Graph invariants, nodes (step/gate/terminal), connections |
| [visits-lifecycle.md](visits-lifecycle.md) | Visit model, lifecycle states, hooks, seal outcomes, closed vs sealed |
| [artifacts.md](artifacts.md) | Output accountability, publishing, consuming, receipts vs artifacts |
| [control-plane.md](control-plane.md) | Checks, policies, actions |
| [capabilities.md](capabilities.md) | Reads, allow, context_budget, paths |
| [registry.md](registry.md) | One full conforming registry document |
| [run-record.md](run-record.md) | Persistence, run status, ledger events, ordering |
| [engine.md](engine.md) | Engine procedure pseudocode |
| [predicate-language.md](predicate-language.md) | Predicate language v2 — fact environment, collections, compile/eval |
| [expressions.md](expressions.md) | v1 expression language (superseded; reference only) |
| [validation.md](validation.md) | Structural vs semantic validation |

**Generated alongside concepts:**

| Document | Contents |
|---|---|
| [../index.md](../index.md) | Generated docs hub — flow, nodes, workers |
| [../flow.md](../flow.md) | Flow graph and connections from `factory-flow.yaml` |
| [../nodes/](../nodes/) | Per-node reference (registry + annotations) |
| [../catalog/workers/](../catalog/workers/) | Worker contract summaries |
| [../cli/index.md](../cli/index.md) | Implemented CLI commands (grows as commands ship) |

---

## Reading order

### Workflow author

1. [README.md](README.md) — charter and conceptual model
2. [graph.md](graph.md) — nodes and connections
3. [visits-lifecycle.md](visits-lifecycle.md) — visit lifecycle
4. [control-plane.md](control-plane.md) — checks, policies, actions
5. [artifacts.md](artifacts.md) — declared outputs and publication
6. [capabilities.md](capabilities.md) — reads, allow, paths
7. [registry.md](registry.md) — integrated example
8. [validation.md](validation.md) — structural and semantic rules
9. [../flow.md](../flow.md) — current implementation flow instance

### Engine implementer

1. [README.md](README.md) — charter and guarantees
2. [graph.md](graph.md) — routing invariants
3. [visits-lifecycle.md](visits-lifecycle.md) — lifecycle hooks and seal outcomes
4. [control-plane.md](control-plane.md) — check evaluation and actions
5. [engine.md](engine.md) — procedure pseudocode
6. [run-record.md](run-record.md) — ledger and persistence
7. [predicate-language.md](predicate-language.md) — condition language
8. [validation.md](validation.md) — structural and semantic rules
9. [../cli/index.md](../cli/index.md) — implemented CLI surface

### Auditor

1. [README.md](README.md) — governing contract
2. [run-record.md](run-record.md) — authoritative ledger
3. [visits-lifecycle.md](visits-lifecycle.md) — lifecycle and seal semantics
4. [artifacts.md](artifacts.md) — output accountability
5. [control-plane.md](control-plane.md) — check and policy audit trail
