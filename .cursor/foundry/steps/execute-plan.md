# execute.plan

Record execution graph and phase brief evidence without a planner model on the default host path.

## Preconditions

- `feature_branch` set (`feature-branch-set` on examine).
- `execution_graph_id` reference present (`ensure-execution-graph-reference` on open — set during `execute.branch`).

## Host behavior

1. Build minimal `execution-graph.json` with `graph_id`, `approved_ac_digest`, and a single default work item.
2. Publish `execution-graph` and `execute-brief` artifacts under `run:artifacts/{visit_id}/`.
3. Patch `execution_graph_id` and `execute_brief_path`.
4. Seal `registry:schemas/agent-receipt.schema.json` (engine planner mode).
5. `transition` to `execute.build`.

## Steward / operator

Use `run advance` after landing on `execute.plan`. Planner worker prompts apply only when a task binding is used outside the host-owned path.
