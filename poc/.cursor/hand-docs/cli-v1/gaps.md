# CLI v1 — design gaps

Status: **draft plan**

These are conflicts between [cli.md](cli.md), [cli-walkthrough.md](cli-walkthrough.md), [workflow-schema-v1](../workflow-schema-v1/README.md), [v1-spec.md](../v1-spec.md), and `.cursor/foundry/flows/factory-flow.yaml`. Wording fixes stay in the group specs. Each item below needs a design choice before implementation.

---

## 1. One owner for builder commits

**Conflict.** [v1-spec.md](../v1-spec.md) (`execute.build`) says the builder calls `visit transition` with a summary and the CLI commits on `feature_branch`. [cli-visit.md](cli-visit.md) has `--commit` on that command. [cli-build.md](cli-build.md) `build build` also creates the accountability commit and does not seal the visit.

**Plan.**

1. Pick `visit transition --commit` as the only git commit for a work item, matching the product spec.
2. Keep `build build` as "run the next ready work item" without `git commit`.
3. Keep `build test` and `build validate-exit` as read-only or process runners. They do not commit.
4. Record the commit SHA on the work-item receipt before `receipt.linked`, so the seal check can see it.
5. Delete the duplicate path from `cli-build.md` and the PoC mapping once that choice is written into `factory-flow.yaml` `allow.cli`.

## 2. Steward commands must match `allow.cli`

**Conflict.** [capabilities.md](../workflow-schema-v1/capabilities.md) allows a steward to invoke only ids on the active node. Step default is `["transition"]`. `shape.intake` lists `artifact.publish` and `transition` only. [cli-walkthrough.md](cli-walkthrough.md) still shows stewards running `app validate`, `check eval`, `git clean-check`, `branch create`, and `build test` on nodes that do not list those ids. `execute.branch` has no `branch.create`.

**Plan.**

1. Split each [cli-walkthrough.md](cli-walkthrough.md) row into **engine hook** or **steward capability**.
2. Probes that already exist as catalog checks (`validate-manifest`, `validate-git-clean-execute`, `validate-build-exit`, `ensure-execution-graph-reference`) stay engine-only. Remove them from the steward command column.
3. For real steward tools (`branch.create`, `artifact.publish`, `receipt.link`, `build.build`, `build.test`), add the id to that node's `allow.cli` in `factory-flow.yaml`, or move the work into the engine hook.
4. Re-read [cli-walkthrough.md](cli-walkthrough.md) against the YAML after the allow lists change.

## 3. `intake-receipt-sealed` is visit-scoped

**Conflict.** The check counts `receipt.linked` where `visit_id=visit.id`. `execute.intake.gate` and `verify.intake.gate` run that check on **their** visit. The receipt is linked on the intake **step** visit. The gate visit id does not match, so the gate check cannot see the step receipt. Gate `allow.cli` is empty, so the steward cannot seal a second receipt there.

**Plan.**

1. Change the gate checks to count the receipt on the prior intake visit (for example `history.last('visit.sealed', node_id='execute.intake')` plus a receipt filter), **or** link the receipt in a way the gate expression can see without using `visit.id`.
2. Update [cli-receipt.md](cli-receipt.md) and [cli-git.md](cli-git.md) so they stop saying the gate `on_examine` check is satisfied by the intake-step receipt as written today.
3. Add a semantic validation rule: a check referenced from node B must not require `visit.id` evidence that only node A can publish, unless B is the same visit.

## 4. Engine gate decisions are not in the registry

**Conflict.** [cli-gate.md](cli-gate.md) describes automatic decisions for `execute.test.gate` (`pass` | `repair`) and `verify.acceptance.gate` (`pass` | `replan` | `reshape` | `rework_execute`). In `factory-flow.yaml` those gates mostly check that a prior visit sealed. They do not map a test exit or an acceptance result onto `produces.options`.

**Plan.**

1. For each `decider: engine` gate, add the check or expression that selects exactly one option.
2. Document that expression in [cli-gate.md](cli-gate.md) only after it exists in the YAML.
3. v1 has no `decider: worker` nodes. Leave worker gates out of the CLI until a node uses them.

## 5. Acceptance failure must not admit later verify steps

**Conflict.** [v1-spec.md](../v1-spec.md) says acceptance failure skips `verify.code_quality` and `verify.code_review`. The CLI rework section routes `replan`, `reshape`, and `rework_execute` away from those nodes, but it never states that a failed acceptance does not admit them.

**Plan.**

1. Confirm `factory-flow.yaml` has no connection from a failing acceptance decision to `verify.code_quality` or `verify.code_review`.
2. Add one sentence to the rework section: those visits are admitted only after `verify.acceptance.gate` resolves `pass` (or after `verify.code_quality` seals `not_applicable` when review is disabled, which still requires acceptance `pass`).
3. Keep `skip` on `verify.code_quality` for `config.review.enabled == false`. That path is separate from acceptance failure.

## 6. Run record vs PoC state schema

**Conflict.** [run-record.md](../workflow-schema-v1/run-record.md) makes the ledger authoritative. `factory-run-state.schema.json` still requires PoC fields such as `current_step`. [v1-spec.md](../v1-spec.md) still describes `actions.on_enter` and `state_json.permissions`. The workflow schema uses `lifecycle.on_*` and `allow.state`.

**Plan.**

1. Define the v1 snapshot as a projection of the ledger: active visit id, lifecycle, run status, and domain keys from `allow.state`.
2. `run show` reads that projection. `run resume` rebuilds it from the ledger.
3. Update the product-spec registry field table to the schema names. Leave the CLI visit-centric.
4. Do not add a `handoff` ledger type unless [run-record.md](../workflow-schema-v1/run-record.md) lists it. `run handoff` can write a resume packet file without a new event type.

## 7. Product commands and missing operator commands

**Incomplete.** [v1-spec.md](../v1-spec.md) requires `/craft-init`, `/craft-shape`, `/craft-execute`, `/craft-resume`, and `/craft-status`, plus dry-run for the eval harness. The CLI specs map some of this (`app discover` / `init`, `run create`, `run resume`, `run show`, `--dry-run`) and omit `run list`, `run latest`, and `run block` that the PoC mapping used to claim.

**Plan.**

1. Add a short table in [cli.md](cli.md): each `/craft-*` command, the `foundry` argv it wraps, and the phase chat rule (execute and verify are new chats; verify auto-starts with a human CTA fallback).
2. Decide whether operators need `run list` and `run latest`. If yes, add them to [cli-run.md](cli-run.md). If no, leave the PoC rows as "not in v1".
3. Specify `--dry-run`: no ledger append; say whether read-only probes (`app validate`, `git clean-check`) still run.
4. Specify `deliver.stub`: explicit `visit transition` versus engine auto-seal. The schema allows a terminal node with no outgoing connections; the product spec says the CLI is invoked at `verify.complete`, not that the stub auto-seals.

## 8. Receipt and artifact paths

**Incomplete.** Three path stories exist for `ticket.json`: `run:artifacts/{visit_id}/ticket.json` in the flow YAML, `{run_dir}/ticket.json` in the product spec, and `workspace:.foundry/tmp/...` in some CLI samples. [artifacts.md](../workflow-schema-v1/artifacts.md) is the rule: publish with `publish_artifact`, bare paths are invalid, roots are `registry:`, `run:`, and `workspace:`.

**Plan.**

1. Use the YAML `uri` as the published artifact URI.
2. Keep receipt files under `run:receipts/` with schema `registry:schemas/...`.
3. Replace sample `--file workspace:.foundry/tmp/...` paths when they are only scratch input; the ledger URI is the `run:` path after seal.

---

## Suggested order

1. Receipt visit scope (breaks gate checks as authored).
2. `allow.cli` vs [cli-walkthrough.md](cli-walkthrough.md) (breaks capability enforcement).
3. Builder commit owner (product spec vs `build build`).
4. Engine gate decision expressions.
5. Acceptance short-circuit sentence, snapshot schema, `/craft-*` table, path cleanup.
