"""Multi-chat handoff: run list/latest/handoff, resume-packet, gate policy, learning finalize."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import foundry_protocol

INTERACTION_MODES = ("interactive", "drive_to_pr", "plan_control")

# step_id -> (auto_decision or None if never auto, extra predicate name)
# Predicates evaluated in gate_auto_decision.
AUTO_GATE_POLICY: dict[str, dict[str, Any]] = {
    "intake.grill": {
        "modes": ("drive_to_pr", "plan_control"),
        "decision": "approve",
        "require": "grill_resolved",
    },
    "plan.brief": {
        "modes": ("drive_to_pr",),
        "decision": "approve",
        "require": "brief_recorded",
    },
    "plan.graph": {
        "modes": ("drive_to_pr",),
        "decision": "approve",
        "require": "graph_validated",
    },
    "implement.devops_review": {
        "modes": ("drive_to_pr", "plan_control"),
        "decision": "approve",
        "require": "devops_empty_or_ok",
    },
    "implement.documentation": {
        "modes": ("drive_to_pr", "plan_control"),
        "decision": "approve",
        "require": "doc_report_received",
    },
    "deliver.scope_comment": {
        "modes": ("drive_to_pr", "plan_control"),
        "decision": "skip",
        "require": "scope_empty",
    },
}

HARD_STOP_STEPS = {
    "intake.present_ac",
    "intake.approve_ac",
    "implement.code_review",
    "implement.pre_pr_review",
    "deliver.ship",
}

HANDOFF_BLURBS: dict[str, str] = {
    "intake.jira": "Ticket intake in progress; finish board pick or load issue.",
    "intake.local": "Load local markdown ticket; then pivot.",
    "intake.free_text": "Free-text intake; capture feature statement and app.",
    "intake.pivot": "Resolve run mode and risk tier.",
    "intake.refine": "Run story-writer refine; then grill or present AC.",
    "intake.grill": "Resolve grilling questions; then present AC.",
    "intake.present_ac": "Present AC in full; await human approval.",
    "intake.approve_ac": "Freeze approved_ac; then research.",
    "plan.research": "Launch codebase-researcher; then brief.",
    "plan.brief": "Planner writes brief.md; gate then graph.",
    "plan.graph": "Planner writes execution-graph.json; then branch.",
    "implement.branch": "Create feature branch; then build.",
    "implement.build": "Dispatch builders; build-step verify; then validate.",
    "implement.validate": "Run implementation-validator; then code review.",
    "implement.code_review": "Human code review (ready-for-PR); then devops/pre_pr/docs.",
    "implement.devops_review": "DevOps pre-PR review; then continue.",
    "implement.pre_pr_review": "Bugbot/security; then documentation.",
    "implement.documentation": "Documentation-writer; then delivery-check.",
    "deliver.gate": "Run delivery-check; then scope comment / ship.",
    "deliver.scope_comment": "Post or skip out-of-scope Jira comment; then ship.",
    "deliver.ship": "Commit, push, PR; confirm; finalize-learning.",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def interaction_mode_of(state: dict[str, Any], config: dict[str, Any] | None = None) -> str:
    mode = state.get("interaction_mode")
    if isinstance(mode, str) and mode in INTERACTION_MODES:
        return mode
    if isinstance(config, dict):
        foundry = config.get("foundry") if isinstance(config.get("foundry"), dict) else {}
        orch = foundry.get("orchestrator") if isinstance(foundry.get("orchestrator"), dict) else {}
        default = orch.get("default_interaction_mode")
        if isinstance(default, str) and default in INTERACTION_MODES:
            return default
    return "interactive"


def _step_evidence(state: dict[str, Any], step_id: str) -> dict[str, Any]:
    steps = state.get("steps") if isinstance(state.get("steps"), dict) else {}
    evidence = steps.get(step_id)
    return evidence if isinstance(evidence, dict) else {}


def predicate_ok(
    name: str,
    state: dict[str, Any],
    run_dir: Path,
    *,
    extras: dict[str, Any] | None = None,
) -> bool:
    extras = extras or {}
    if name == "grill_resolved":
        unresolved_ok = int(state.get("grilling_unresolved_count") or 0) == 0
        # Auto-approve only when refine left no clarifying questions (prevents steward self-settle).
        clarifying_ok = int(state.get("clarifying_questions_count") or 0) == 0
        return unresolved_ok and clarifying_ok
    if name == "brief_recorded":
        snap = state.get("brief_snapshot")
        return isinstance(snap, dict) and bool(snap.get("hash"))
    if name == "graph_validated":
        # Require explicit --graph-validated after a successful `graph validate`.
        # File presence alone is not enough (parent must not auto-approve a draft).
        return extras.get("graph_validated") is True
    if name == "devops_empty_or_ok":
        return extras.get("devops_empty") is True or extras.get("force") is True
    if name == "doc_report_received":
        evidence = _step_evidence(state, "implement.documentation")
        return evidence.get("report") == "received"
    if name == "scope_empty":
        register = state.get("pr_extras_register")
        return not register
    return False


def gate_auto_decision(
    step_id: str,
    state: dict[str, Any],
    config: dict[str, Any] | None,
    run_dir: Path,
    *,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return {decision, source: auto} when interaction_mode allows auto for this step."""
    mode = interaction_mode_of(state, config)
    if mode == "interactive":
        return None
    policy = AUTO_GATE_POLICY.get(step_id)
    if not policy or mode not in policy["modes"]:
        return None
    require = policy.get("require")
    if require and not predicate_ok(str(require), state, run_dir, extras=extras):
        return None
    return {"decision": policy["decision"], "source": "auto", "step_id": step_id}


def gate_policy_for_step(
    step_id: str,
    state: dict[str, Any],
    config: dict[str, Any] | None,
    step_meta: dict[str, Any] | None,
    run_dir: Path,
) -> dict[str, Any]:
    mode = interaction_mode_of(state, config)
    gate = (step_meta or {}).get("gate") if isinstance(step_meta, dict) else None
    if not gate:
        return {"kind": "none", "auto_eligible": False, "auto_decision": None, "prompt_key": None}
    if gate.get("kind") == "evidence_only":
        return {
            "kind": "evidence_only",
            "auto_eligible": False,
            "auto_decision": None,
            "prompt_key": gate.get("prompt_key"),
        }
    auto = gate_auto_decision(step_id, state, config, run_dir)
    if auto:
        return {
            "kind": "auto_eligible",
            "auto_eligible": True,
            "auto_decision": auto["decision"],
            "prompt_key": gate.get("prompt_key"),
        }
    return {
        "kind": "hard",
        "auto_eligible": False,
        "auto_decision": None,
        "prompt_key": gate.get("prompt_key"),
        "interaction_mode": mode,
    }


def session_stop_hint(
    step_id: str,
    gate_policy: dict[str, Any],
    *,
    has_subagent: bool = False,
) -> str:
    if step_id == "implement.build":
        return "stop_after_build_verify"
    if gate_policy.get("kind") == "hard" or step_id in HARD_STOP_STEPS:
        return "stop_after_hard_gate"
    if has_subagent:
        return "stop_after_worker"
    if gate_policy.get("kind") == "auto_eligible":
        return "continue"
    return "continue"


def valid_intents_for_step(step_id: str, state: dict[str, Any]) -> list[str]:
    intents = ["resume"]
    graph = _step_evidence(state, "plan.graph")
    if graph.get("human_approved") or state.get("execution_graph_id"):
        intents.append("administer")
    if step_id.startswith("deliver."):
        intents.append("ship")
    if state.get("interaction_mode") == "plan_control" and step_id in (
        "plan.brief",
        "plan.graph",
        "implement.build",
    ):
        if "administer" not in intents:
            intents.append("administer")
    return intents


def step_inputs(step_id: str, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "approved_ac_version": state.get("approved_ac_version"),
        "risk_tier": state.get("risk_tier"),
        "readiness": state.get("readiness"),
    }
    brief = state.get("brief_snapshot")
    if isinstance(brief, dict):
        inputs["brief_path"] = brief.get("path") or state.get("brief_path")
        inputs["brief_hash"] = brief.get("hash")
    elif state.get("brief_path"):
        inputs["brief_path"] = state.get("brief_path")
    graph_path = run_dir / "execution-graph.json"
    if graph_path.is_file():
        inputs["execution_graph_path"] = str(graph_path)
        inputs["execution_graph_id"] = state.get("execution_graph_id")
    research = _step_evidence(state, "plan.research")
    if research.get("receipt_id"):
        inputs["research_receipt_id"] = research.get("receipt_id")
        inputs["research_receipt_path"] = str(run_dir / "receipts" / f"{research['receipt_id']}.json")
    build = _step_evidence(state, "implement.build")
    if build.get("receipt_id"):
        inputs["build_receipt_id"] = build.get("receipt_id")
    validate = _step_evidence(state, "implement.validate")
    if validate.get("receipt_id"):
        inputs["validate_receipt_id"] = validate.get("receipt_id")
    if step_id.startswith("intake."):
        inputs["draft_ac_count"] = len(state.get("draft_ac") or [])
        inputs["presented_ac_count"] = len(state.get("presented_ac") or [])
        inputs["grilling_unresolved_count"] = state.get("grilling_unresolved_count")
    if step_id.startswith("deliver."):
        inputs["pr_extras_count"] = len(state.get("pr_extras_register") or [])
        inputs["feature_branch"] = state.get("feature_branch")
    if step_id == "implement.build":
        inputs["open_subagent_launches"] = state.get("open_subagent_launches") or []
    return {k: v for k, v in inputs.items() if v is not None}


def list_runs(app_folder: Path) -> dict[str, Any]:
    runs_root = app_folder / ".foundry" / "runs"
    items: list[dict[str, Any]] = []
    if not runs_root.is_dir():
        return {"app_folder": str(app_folder), "runs": items}
    for child in sorted(runs_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        state_path = child / "state.json"
        if not state_path.is_file():
            continue
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if state.get("pr_url") and _step_evidence(state, "deliver.ship").get("status") == "completed":
            continue
        if state.get("outcome_status") == "abandoned":
            continue
        items.append(
            {
                "run_id": state.get("run_id"),
                "issue_key": state.get("issue_key"),
                "current_step": state.get("current_step"),
                "interaction_mode": state.get("interaction_mode"),
                "updated_at": state.get("updated_at"),
                "blocked": state.get("blocked"),
                "state_path": str(state_path),
                "run_dir": str(child),
            }
        )
    return {"app_folder": str(app_folder), "runs": items}


def latest_run(app_folder: Path, issue_key: str | None = None) -> dict[str, Any]:
    listed = list_runs(app_folder)
    runs = listed["runs"]
    if issue_key:
        runs = [r for r in runs if r.get("issue_key") == issue_key]
    if not runs:
        return {
            "app_folder": str(app_folder),
            "issue_key": issue_key,
            "run": None,
            "message": "No open runs found.",
        }
    return {"app_folder": str(app_folder), "issue_key": issue_key, "run": runs[0]}


def write_handoff(
    *,
    state: dict[str, Any],
    run_dir: Path,
    state_path: Path,
    next_commands: list[str] | None = None,
    what_happened: str | None = None,
    what_next: str | None = None,
) -> dict[str, Any]:
    step = str(state.get("current_step") or "")
    mode = interaction_mode_of(state)
    blurb = HANDOFF_BLURBS.get(step, f"Continue at {step}.")
    kickoff = (
        f"Use foundry. Intent: resume. App: {state.get('app_folder')}. Run: {state.get('run_id')}."
    )
    payload = {
        "schema_version": foundry_protocol.PROTOCOL_VERSION,
        "run_id": state.get("run_id"),
        "issue_key": state.get("issue_key"),
        "app_folder": state.get("app_folder"),
        "run_dir": str(run_dir),
        "state_path": str(state_path),
        "current_step": step,
        "interaction_mode": mode,
        "blocked": state.get("blocked"),
        "feature_branch": state.get("feature_branch"),
        "what_happened": (what_happened or f"Stopped at {step}.")[:2000],
        "what_next": (what_next or blurb)[:2000],
        "kickoff_prompt": kickoff,
        "next_commands": next_commands or [],
        "updated_at": now_iso(),
        "conversation_checkpoint": {
            "required": isinstance(state.get("session_stop_obligation"), dict),
            "source_conversation_id": state.get("active_conversation_id"),
        },
    }
    foundry_protocol.validate_schema(
        payload,
        "packets/handoff.schema.json",
        artifact="handoff",
    )
    handoff_json = run_dir / "handoff.json"
    handoff_md = run_dir / "handoff.md"
    handoff_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md = "\n".join(
        [
            "---",
            f"run_id: {payload['run_id']}",
            f"current_step: {step}",
            f"interaction_mode: {mode}",
            f"issue_key: {payload.get('issue_key')}",
            f"feature_branch: {payload.get('feature_branch')}",
            f"blocked: {json.dumps(payload.get('blocked'))}",
            "---",
            "",
            "# Foundry handoff",
            "",
            f"**What happened:** {payload['what_happened']}",
            "",
            f"**What next:** {payload['what_next']}",
            "",
            "## Kickoff (paste into a new Agent chat)",
            "",
            "```text",
            kickoff,
            "```",
            "",
            "## Next commands",
            "",
        ]
        + ([f"- `{c}`" for c in (next_commands or [])] or ["- (run `flow resume-packet` / `flow orchestrator-packet`)"])
        + [
            "",
            "Do not load full events.jsonl or all receipts. Use resume-packet only.",
            "",
        ]
    )
    handoff_md.write_text(md, encoding="utf-8")
    return {
        "handoff_json": str(handoff_json),
        "handoff_md": str(handoff_md),
        "kickoff_prompt": kickoff,
        "handoff": payload,
    }


def build_learning_record(
    state: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    outcome_status: str,
    pr_url: str | None = None,
    abandon_reason: str | None = None,
    foundry_git_sha: str | None = None,
) -> dict[str, Any]:
    created = state.get("created_at")
    updated = state.get("updated_at") or now_iso()
    duration_ms = None
    try:
        if created and updated:
            c = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            u = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
            duration_ms = int((u - c).total_seconds() * 1000)
    except ValueError:
        duration_ms = None

    failure_classes: dict[str, int] = {}
    gate_source_hist: dict[str, int] = {"human": 0, "auto": 0}
    handoff_count = 0
    session_boundaries: list[dict[str, Any]] = []
    subagent_invocations: dict[str, int] = {}
    critic_tags: list[str] = []
    auto_gate_steps: set[str] = set()
    auto_gate_overturns: list[dict[str, Any]] = []
    gate_presented_at: dict[str, datetime] = {}
    gate_wait_ms: dict[str, int] = {}
    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event.get("event_type") == "failure_classified":
            fc = payload.get("failure_class")
            if isinstance(fc, str):
                failure_classes[fc] = failure_classes.get(fc, 0) + 1
        if event.get("event_type") == "gate_resolved":
            src = payload.get("gate_source") or payload.get("source") or "human"
            if src not in gate_source_hist:
                gate_source_hist[src] = 0
            gate_source_hist[str(src)] += 1
            step_id = str(event.get("step_id") or "")
            if src == "auto":
                auto_gate_steps.add(step_id)
            elif step_id in auto_gate_steps:
                auto_gate_overturns.append(
                    {"step_id": step_id, "decision": payload.get("decision")}
                )
            try:
                resolved_at = datetime.fromisoformat(str(event.get("timestamp")).replace("Z", "+00:00"))
                if step_id in gate_presented_at:
                    gate_wait_ms[step_id] = int(
                        (resolved_at - gate_presented_at[step_id]).total_seconds() * 1000
                    )
            except (TypeError, ValueError):
                pass
        if event.get("event_type") == "gate_presented":
            step_id = str(event.get("step_id") or "")
            try:
                gate_presented_at[step_id] = datetime.fromisoformat(
                    str(event.get("timestamp")).replace("Z", "+00:00")
                )
            except (TypeError, ValueError):
                pass
        if event.get("event_type") == "handoff_written":
            handoff_count += 1
            session_boundaries.append(
                {
                    "step_id": event.get("step_id"),
                    "timestamp": event.get("timestamp"),
                    "session_id": payload.get("session_id"),
                    "fulfilled_obligation": payload.get("fulfilled_obligation"),
                }
            )
        if event.get("event_type") == "subagent_launched":
            agent = str(payload.get("agent") or "unknown")
            subagent_invocations[agent] = subagent_invocations.get(agent, 0) + 1
            if agent in ("bugbot", "security-review") and agent not in critic_tags:
                critic_tags.append(agent)

    required = [
        "outcome",
        "rework",
        "failure_class_distribution",
        "gate_source_histogram",
    ]
    return {
        "schema_version": foundry_protocol.PROTOCOL_VERSION,
        "run_id": state.get("run_id"),
        "issue_key": state.get("issue_key"),
        "app_folder": state.get("app_folder"),
        "interaction_mode": interaction_mode_of(state),
        "resolved_profile_hash": state.get("resolved_profile_hash"),
        "foundry_git_sha": foundry_git_sha,
        "outcome": {
            "status": outcome_status,
            "pr_url": pr_url or state.get("pr_url"),
            "duration_ms": duration_ms,
            "abandon_reason": abandon_reason,
        },
        "rework": state.get("rework") or {},
        "failure_class_distribution": failure_classes,
        "gate_source_histogram": gate_source_hist,
        "auto_gate_overturns": auto_gate_overturns,
        "session_boundaries": session_boundaries,
        "seam_friction": [
            {
                "step_id": step_id,
                "rework_loops": int((state.get("rework") or {}).get(step_id) or 0),
                "gate_wait_ms": wait_ms,
            }
            for step_id, wait_ms in sorted(gate_wait_ms.items())
        ],
        "assumption_ledger": list(state.get("assumptions") or []),
        "critic_tags": critic_tags,
        "critic_taxonomy": {
            tag: sum(
                1
                for event in events
                if event.get("event_type") in ("subagent_completed", "subagent_failed")
                and (event.get("payload") or {}).get("agent") == tag
            )
            for tag in critic_tags
        },
        "escaped_defects": list(state.get("escaped_defects") or []),
        "seams": [],
        "reliability_in_scope": None,
        "subagent_invocations": subagent_invocations,
        "required_fields": required,
        "best_effort": {"handoff_count": handoff_count},
        "created_at": now_iso(),
    }


def write_learning_review(record: dict[str, Any], path: Path) -> None:
    outcome = record.get("outcome") or {}
    lines = [
        "# Learning review",
        "",
        f"- Run: `{record.get('run_id')}`",
        f"- Issue: `{record.get('issue_key')}`",
        f"- Mode: `{record.get('interaction_mode')}`",
        f"- Outcome: **{outcome.get('status')}**",
        f"- PR: {outcome.get('pr_url') or 'n/a'}",
        f"- Duration ms: {outcome.get('duration_ms')}",
        f"- Rework: `{json.dumps(record.get('rework') or {})}`",
        f"- Failure classes: `{json.dumps(record.get('failure_class_distribution') or {})}`",
        f"- Gate sources: `{json.dumps(record.get('gate_source_histogram') or {})}`",
        "",
        "Do not paste this file into a steward chat. Promote distilled knowledge offline.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
