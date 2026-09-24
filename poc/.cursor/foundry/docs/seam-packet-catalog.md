# Seam packet catalog (Foundry v2)

Contract for what each implementation step consumes and produces so a different steward chat can resume without chat history. CLI (`flow resume-packet`, `run handoff`, `worker builder-packet`) must match this document.

**Status legend:** Exists | Gap | Oversize
**Token budgets** are soft caps for steward/worker context, not hard engine limits.

## Envelope schemas

| Packet | Schema | Purpose |
|--------|--------|---------|
| Resume | `schemas/packets/resume-packet.schema.json` | Step-scoped steward packet |
| Handoff | `schemas/packets/handoff.schema.json` | `{run_dir}/handoff.md` + `handoff.json` |
| Learning | `schemas/packets/learning-record.schema.json` | Offline post-run record |
| Ticket | `schemas/packets/ticket.schema.json` | Sealed `{run_dir}/ticket.json` |
| Craft | `schemas/packets/agent-craft.schema.json` | Worker craft overlay (`staging/{launch_id}.craft.json`) |
| Worker launch | `schemas/packets/worker-launch-packet.schema.json` | Generated bounded Task packet plus craft/telemetry contract |

## Cross-cutting rules

- Orchestrator loads **only** `resume-packet` fields for `current_step` + the step unit markdown. Never dump full `events.jsonl` or all receipts.
- Incomplete `open_subagent_launches` → complete or `run block`; never double-launch.
- Working tree: packet records `feature_branch` + expected HEAD when set; resume warns on mismatch.
- Learning fields accumulate at gate resolve / transition / complete; stewards do **not** load prior `learning_record.json`.
- Every worker launch uses `worker launch-packet`; workers write only `craft_staging_path`. Parent must not write craft, receipts, `brief.md`, or `execution-graph.json`.
- Every steward records the host-provided conversation ID with `cursor session-record` after run creation/resume. A different post-handoff ID proves freshness; when the source ID was unavailable, the first non-empty post-handoff ID fulfills the obligation as recovery without claiming proof.
- Runtime packets are protocol `2.2.0`; earlier run artifacts are intentionally
  rejected. Profiles and ticket packets retain independent `1.0.0` formats.
- Graph auto-gate requires `gate resolve --graph-validated` after successful `graph validate` (file presence alone is insufficient).

---

## 1. Boot (`cli resolve` / `run init`)

| Field | Value |
|-------|-------|
| step_id | `(pre-run)` |
| resume_intent | `new` |
| orchestrator_loads | factory_root, profile path |
| orchestrator_must_not_load | prior run receipts |
| inputs_from_prior | none |
| produces_on_disk | `{run_dir}/state.json`, `config.json`, `ticket.json` (when sealed), `events.jsonl`, `receipts/` |
| state_keys_written | run_id, run_mode, current_step, interaction_mode, resolved_profile_hash, … |
| receipt_shape | none |
| human_gate | none |
| session_stop | no |
| handoff_blurb | Run initialized; continue at entry step. |
| token_budget | orchestrator ≤ 40 lines |
| done_means | `run init` success; state_path exists |
| Status | Exists |

**Delivered:** Immutable `config.json` + hash; mutable `state.json` starting at flow entry.

---

## 2. `intake.jira` / `intake.local` / `intake.free_text` → `intake.pivot`

| Field | Value |
|-------|-------|
| step_id | `intake.jira` / `intake.local` / `intake.free_text` |
| resume_intent | `new`, `resume` |
| orchestrator_loads | config intake/jira/workspace slice; ticket key, local file, or free text |
| orchestrator_must_not_load | unrelated runs |
| inputs_from_prior | interaction_mode |
| produces_on_disk | state updates only; local path may copy nothing beyond state |
| state_keys_written | issue_key, app_folder, developer_first_name, ticket_source, atlassian_source (jira) |
| receipt_shape | none |
| human_gate | board/local pick stop when listing |
| session_stop | if-hard-gate (after list until pick) |
| handoff_blurb | Ticket/app resolved; run pivot. |
| token_budget | ≤ 60 lines |
| done_means | issue_key or free-text packet; app_folder set; ticket_source set; step status completed |
| Status | Exists |

**Delivered:** Ticket identity (`jira` | `local` | `chat`) and app folder for the rest of the run.

**Local:** `ticket list|load|pick`; id = markdown filename stem; no Atlassian calls.

---

## 3. `intake.pivot` → `intake.refine`

| Field | Value |
|-------|-------|
| step_id | `intake.pivot` |
| resume_intent | `resume` |
| orchestrator_loads | issue type, analysis config |
| produces_on_disk | state only |
| state_keys_written | run_mode, risk_tier, risk_tier_source, pr_extras_register |
| human_gate | none (risk override optional) |
| session_stop | no |
| handoff_blurb | Mode and risk set; refine story. |
| token_budget | ≤ 30 lines |
| done_means | run_mode + risk_tier set |
| Status | Exists |

---

## 4. `intake.refine` → `intake.grill` \| `intake.present_ac`

| Field | Value |
|-------|-------|
| step_id | `intake.refine` |
| resume_intent | `resume` |
| orchestrator_loads | ticket packet; story-writer config |
| orchestrator_must_not_load | full repo |
| inputs_from_prior | issue_key, app_folder |
| produces_on_disk | receipts/{id}.json |
| state_keys_written | draft_ac, readiness, clarifying_questions_count, steps.intake.refine.* |
| receipt_shape | story-writer; summary_markdown ≤ 4k chars |
| human_gate | none |
| session_stop | yes (`stop_after_worker`) |
| handoff_blurb | Draft AC ready; grill or present. |
| token_budget | steward ≤ 40; worker ≤ 8k |
| done_means | receipt completed; draft_ac present |
| Status | Exists |

---

## 5. `intake.grill` → `intake.present_ac`

| Field | Value |
|-------|-------|
| step_id | `intake.grill` |
| resume_intent | `resume` |
| orchestrator_loads | draft_ac, readiness, risk_tier; grill receipt summary |
| orchestrator_must_not_load | full exploration dumps beyond receipt |
| produces_on_disk | grill receipt |
| state_keys_written | assumptions, grilling_decisions, grilling_unresolved_count, steps.intake.grill.* |
| receipt_shape | grilling; questions_generated + decisions |
| human_gate | hard if unresolved>0 or clarifying_questions_count>0; auto-eligible only when both are 0 (`drive_to_pr`, `plan_control`) |
| session_stop | yes (`stop_after_worker` / hard gate); obligation remains until handoff plus a different host-provided conversation ID |
| handoff_blurb | Grill resolved; present AC. |
| token_budget | steward ≤ 50; summary ≤ 3k |
| done_means | human_approved or auto; unresolved handled |
| Status | Exists |

---

## 6. `intake.present_ac` → `intake.approve_ac`

| Field | Value |
|-------|-------|
| step_id | `intake.present_ac` |
| resume_intent | `resume` |
| orchestrator_loads | draft_ac, grilling_decisions; optional `{run_dir}/presented_ac.json` |
| orchestrator_must_not_load | paste entire sections 1–7 into every resume (Oversize) — prefer file + AskQuestion |
| produces_on_disk | presented_ac in state; optional presented_ac.json |
| state_keys_written | presented_ac, steps.intake.present_ac.* |
| human_gate | hard (all modes) |
| session_stop | yes (hard gate) |
| handoff_blurb | AC presented; await approve. |
| token_budget | steward chat ≤ 80 lines pointing at file |
| done_means | human_approved; presented_ac non-empty |
| Status | Exists / Oversize presentation |

**Primary handoff seam (with approve):** scope freeze boundary.

---

## 7. `intake.approve_ac` → `plan.research`

| Field | Value |
|-------|-------|
| step_id | `intake.approve_ac` |
| resume_intent | `resume` |
| orchestrator_loads | presented_ac |
| produces_on_disk | state |
| state_keys_written | approved_ac, approved_ac_version, steps.intake.approve_ac.* |
| human_gate | hard (all modes) |
| session_stop | yes |
| handoff_blurb | AC frozen; start research. |
| token_budget | ≤ 40 lines |
| done_means | approved_ac_version ≥ 1; verbatim match |
| Status | Exists |

---

## 8. `plan.research` → `plan.brief`

| Field | Value |
|-------|-------|
| step_id | `plan.research` |
| resume_intent | `resume` |
| orchestrator_loads | approved_ac; app_folder |
| orchestrator_must_not_load | unrelated packages |
| produces_on_disk | research receipt |
| state_keys_written | steps.plan.research.* |
| receipt_shape | codebase-researcher implementation; summary extract for brief |
| human_gate | none |
| session_stop | yes (`stop_after_worker`) |
| handoff_blurb | Research done; write brief via planner. |
| token_budget | steward ≤ 30; receipt summary ≤ 4k into brief agent |
| done_means | status completed + receipt_id |
| Status | Exists |

---

## 9. `plan.brief` → `plan.graph`

| Field | Value |
|-------|-------|
| step_id | `plan.brief` |
| resume_intent | `resume` |
| orchestrator_loads | approved_ac; research receipt **summary**; brief path after write |
| produces_on_disk | `{run_dir}/brief.md`; brief_snapshot in state |
| state_keys_written | steps.plan.brief.*, brief_path, brief_snapshot |
| receipt_shape | planner mode `brief`; summary_markdown |
| human_gate | hard in `interactive`/`plan_control`; auto after record-brief in `drive_to_pr` |
| session_stop | yes (`stop_after_worker` / hard gate) |
| handoff_blurb | Brief approved; build execution graph. |
| token_budget | steward ≤ 40 |
| done_means | brief.md exists; plan record-brief ok; human_approved or auto |
| Status | Exists (planner `brief` mode owns `brief.md`) |

---

## 10. `plan.graph` → `implement.branch`

| Field | Value |
|-------|-------|
| step_id | `plan.graph` |
| resume_intent | `resume`, `administer` (after approve) |
| orchestrator_loads | brief.md, approved_ac, risk_tier |
| produces_on_disk | `{run_dir}/execution-graph.json` |
| state_keys_written | execution_graph_id, steps.plan.graph.* |
| receipt_shape | planner mode `plan` |
| human_gate | hard interactive/plan_control; auto after graph validate in drive_to_pr; skip if risk low |
| session_stop | yes (`stop_after_worker` / hard gate) |
| handoff_blurb | Graph approved; create feature branch. |
| token_budget | steward ≤ 50 |
| done_means | graph validate exit 0; human_approved or auto |
| Status | Exists (planner `plan` mode owns `execution-graph.json`; parent validates only) |

---

## 11. `implement.branch` → `implement.build`

| Field | Value |
|-------|-------|
| step_id | `implement.branch` |
| resume_intent | `resume` |
| orchestrator_loads | git config, issue_key, developer_first_name |
| produces_on_disk | state; git branch in app repo |
| state_keys_written | default_branch, feature_branch, feature_branch_head (Gap) |
| human_gate | none |
| session_stop | no |
| handoff_blurb | On feature branch; dispatch builders. |
| token_budget | ≤ 30 |
| done_means | feature_branch set ≠ default |
| Status | Exists (+ Gap: HEAD sha) |

---

## 12. `implement.build` (per work item)

| Field | Value |
|-------|-------|
| step_id | `implement.build` |
| resume_intent | `resume`, `administer` |
| orchestrator_loads | worker next-builder / builder-packet only |
| orchestrator_must_not_load | all receipts; app source edits |
| inputs_from_prior | feature_branch, execution-graph.json, approved_ac |
| produces_on_disk | builder receipts; graph item status |
| state_keys_written | steps.implement.build.*; open launches |
| receipt_shape | backend/client/feature/repairer; files_changed + commands |
| human_gate | none (administer may confirm each item) |
| session_stop | yes (`stop_after_worker` after verify) |
| handoff_blurb | Build verify passed (or blocked); validate next. |
| token_budget | builder packet per dependency_summary_token_budget |
| done_means | all items completed; build-step verify receipt; transition evidence = that receipt |
| Status | Exists |

---

## 13. `implement.build` → `implement.validate`

Covered by build verify receipt. Status: Exists.

---

## 14. `implement.validate` → `code_review` \| build rework

| Field | Value |
|-------|-------|
| step_id | `implement.validate` |
| resume_intent | `resume` |
| orchestrator_loads | approved_ac; graph; builder receipt **summaries** |
| produces_on_disk | validator receipt |
| state_keys_written | steps.implement.validate.* |
| receipt_shape | implementation-validator |
| human_gate | none |
| session_stop | yes (`stop_after_worker`) |
| handoff_blurb | Validation clear; human code review. |
| token_budget | steward ≤ 40 |
| done_means | completed without critical_findings decision |
| Status | Exists |

---

## 15. `implement.code_review` → devops \| pre_pr \| docs

| Field | Value |
|-------|-------|
| step_id | `implement.code_review` |
| resume_intent | `resume` |
| orchestrator_loads | diff command pointer; AC map; validator summary |
| orchestrator_must_not_load | full diff paste every time (Oversize) |
| produces_on_disk | state gate fields |
| human_gate | hard (**ready-for-PR**) all modes |
| session_stop | yes |
| handoff_blurb | Implementation approved; continue pre-PR/docs/ship path. |
| token_budget | steward ≤ 60 |
| done_means | human_approved |
| Status | Exists |

---

## 16. `implement.devops_review`

| Field | Value |
|-------|-------|
| step_id | `implement.devops_review` |
| resume_intent | `resume` |
| produces_on_disk | devops report receipt |
| human_gate | hard interactive; auto approve if empty diff (`drive_to_pr`, `plan_control`) |
| session_stop | yes (`stop_after_worker` / hard gate) |
| handoff_blurb | DevOps cleared; pre-PR or docs. |
| done_means | human_approved or auto |
| Status | Exists |

---

## 17. `implement.pre_pr_review`

| Field | Value |
|-------|-------|
| step_id | `implement.pre_pr_review` |
| resume_intent | `resume` |
| produces_on_disk | critic report path / receipt |
| human_gate | hard (ready-for-PR bundle) |
| session_stop | yes |
| handoff_blurb | Critics resolved; documentation. |
| done_means | human_approved or accept_risk; report received |
| Status | Exists (+ Gap: finding taxonomy tags for learning) |

---

## 18. `implement.documentation` → `deliver.gate`

| Field | Value |
|-------|-------|
| step_id | `implement.documentation` |
| resume_intent | `resume` |
| produces_on_disk | DocChangeReport via receipt; model-specific artifacts (AGENTS/PRD or docs/features) |
| human_gate | hard interactive; auto after receipt unless doc_changes (`drive_to_pr`, `plan_control`) |
| session_stop | yes (`stop_after_worker` / hard gate) |
| handoff_blurb | Docs approved; delivery-check. |
| done_means | report received; human_approved or auto; publication.passed when publication.required (IoT SYNC_PRD) |
| Status | Exists |

---

## 19. `deliver.gate` → `scope_comment` → `ship`

| Field | Value |
|-------|-------|
| step_id | `deliver.gate` / `deliver.scope_comment` / `deliver.ship` |
| resume_intent | `resume`, `ship` |
| orchestrator_loads | delivery-check matrix; pr_extras; branch |
| orchestrator_must_not_load | app Write/StrReplace |
| produces_on_disk | state; authenticated engine-owned PR verification event; PR on remote; learning_record at complete |
| human_gate | delivery-check evidence; scope empty → auto skip; confirm_pr hard |
| session_stop | yes at confirm_pr |
| handoff_blurb | PR confirmed; run complete + finalize-learning. |
| done_means | delivery-check 0; `deliver pr-verify` matches authoritative GitHub head/title/tree to seal; pr_url; run complete; learning_record.json |
| Status | Exists |

---

## Intent × step matrix

| Intent | Valid when |
|--------|------------|
| `new` | no run / explicit new init |
| `resume` | any open run |
| `administer` | after graph approved (any mode) or `plan_control` at plan.graph |
| `ship` | `current_step` in deliver.* and delivery-check would pass (or at deliver.gate) |

## Analysis flow note

Same intake seams; analysis.* steps use research/report/confluence/deliver packets. Interaction modes apply to shared intake gates; analysis-specific autos deferred (implementation-first).
