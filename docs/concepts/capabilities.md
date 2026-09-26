# Read and capability boundaries

Node field definitions appear in [graph.md](graph.md#common-fields). Artifact consumption via `reads.artifacts` is in [artifacts.md](artifacts.md#consuming-artifacts). Path roots are defined under [Paths](#paths).

---

`reads` declares the context supplied to the steward. `allow` declares what the steward may change or invoke. Checks are engine-owned and do not inherit steward write capabilities.

## Steward context

When a visit is `opened`, the steward loads a **context packet** for the active visit. The packet assembles position (`run_id`, `visit_id`, `node_id`, `kind`, lifecycle), resolved **reads**, **allow** grants, **produces** declarations, optional **worker** binding, and the step **instructions** registry path.

`foundry run context` renders this packet in two modes:

| Mode | Flag | Audience | Contents |
|---|---|---|---|
| JSON | `--json` | Programs, schema validation, acceptance tests | Structured envelope per `context-packet.schema.json`; includes `instructions_path` but not inlined instruction text |
| Markdown | `--markdown` | Phase stewards (parent agents) | Single document with metadata sections and step instructions inlined verbatim from `instructions_path` |

`--json` and `--markdown` are mutually exclusive. Stewards SHOULD use `--markdown` and follow one document end-to-end. They MUST NOT load `instructions_path` separately when markdown mode is available.

Step instructions remain the **authoring source** at `.cursor/foundry/nodes/{node-id}/instructions.md` (declared as `instructions` on the node). The CLI is a **renderer** — it reads that file and inlines it without rewriting placeholders such as `{run_id}` or `{visit_id}`.

The **Worker** block lists registry paths only (`prompt`, `contract`, `prompt_path`, `contract_path`, `subagent_type`). The steward still launches worker subagents in a separate turn; the packet does not embed worker prompts.

## Defaults

| Field | Default |
|---|---|
| `reads.config` | `[]` |
| `reads.state` | `[]` |
| `reads.files` | `[]` |
| `reads.artifacts` | `[]` |
| `allow.state` | `[]` beyond implicit node scope |
| `allow.files.write` | `[]` |
| `allow.cli` | `["transition"]` for steps, including terminal steps |
| `allow.cli` on gates | `[]`; recording a decision requests close |
| `allow.agents` | `[]` beyond the bound worker |
| `allow.user.ask` | `false` |
| `allow.user.decide` | `true` only when `kind: gate` and `decider: user`; otherwise `false` |
| `lifecycle` | all hooks present as empty lists |
| `context_budget` | engine default |

The engine grants the active steward write access to `state.nodes.<node_id>.*`. Authors list only additional domain-state paths under `allow.state`.

`transition` lets a steward request close. It does not permit selection of a destination or bypass checks.

`worker` authorizes its bound worker. `allow.agents` lists only additional workers the steward may launch.

All `reads` and `allow` lists contain unique strings. State entries are state paths; file entries use the path grammar below; CLI and agent entries are registered capability ids.

`worker` requires exactly `prompt`, `contract`, and `mode`. Prompt and contract paths MUST resolve to registry files. `receipts` is either one receipt-schema path or a non-empty unique list of receipt-schema paths, and every path MUST resolve. Artifact ids and decision options are non-empty strings unique within their node.

## Worker context budget

`context_budget` bounds generated worker context:

```yaml
context_budget:
  max_input_chars: 24000
  max_summary_chars: 4000
```

Both values MUST be positive integers. The engine default applies when the field is omitted.

---

## Paths

Every file reference uses an explicit root:

| Prefix | Root |
|---|---|
| `registry:` | Flow bundle |
| `run:` | Current run directory |
| `workspace:` | Application repository |

Bare file paths are invalid.

Artifact URI templates MAY contain `{visit_id}`. A path in the producing node's `allow.files.write` MAY contain the same template only when it exactly matches a declared artifact destination. The engine resolves both occurrences to the same visit-scoped path before steward work begins. Other path fields MUST NOT contain template placeholders.
