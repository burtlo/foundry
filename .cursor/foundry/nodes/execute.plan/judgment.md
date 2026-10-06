# Execute plan — judgment

## Purpose

Given sealed `shape.record.plan`, frozen `approved_ac`, and execute branch state, propose an **execution graph** and **execute brief** for the build phase — or BLOCKED when required inputs are missing.

Do not change approved acceptance criteria or reopen shape decisions.

## Output (schema-bound only)

Return a single structured plan result — do not call CLI and do not choose the next workflow node.

- `execution_graph` — JSON object with at least `schema_version`, `graph_id`, `run_id`, `approved_ac_digest`, `feature_branch`, and non-empty `work_items[]` (each item: `id`, `title`, `owner`).
- `execute_brief_markdown` — markdown brief: scope pointer to the sealed plan, feature branch, graph id, and **verbatim** approved AC section.
- `verdict` — `PROCEED` when ready to publish; `BLOCKED` when not.
- `blockers` — required non-empty when `verdict` is `BLOCKED`.
- `summary` — short verdict line (one or two sentences).

Use `execution_graph_id` from run state for `graph_id` when present; otherwise `{run_slug}:execution-graph`.

When `approved_ac` or sealed plan content is missing, use `verdict: BLOCKED` with clear `blockers`.

The host publishes artifacts, patches `execution_graph_id` and `execute_brief_path`, seals the agent receipt, and completes the visit when you return `PROCEED`.
