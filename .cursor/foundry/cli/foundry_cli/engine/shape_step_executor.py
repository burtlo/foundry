"""Host-owned deterministic steps after shape judgment (examine, present, record)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from foundry_cli.constants import EVENT_ARTIFACT_LINKED
from foundry_cli.engine.agent.dispatch import agent_requests_map
from foundry_cli.engine.agent.tasks import (
    SHAPE_EXAMINE_TASK_ID,
    SHAPE_PRESENT_TASK_ID,
    SHAPE_RECORD_TASK_ID,
)
from foundry_cli.engine.examination_state import (
    derive_open_clarifying_questions_count,
    sync_open_clarifying_questions_count,
)
from foundry_cli.engine.intake_executor import (
    AGENT_RECEIPT_SCHEMA,
    _seal_receipt_file,
)
from foundry_cli.engine.lifecycle import transition_visit
from foundry_cli.engine.receipts import find_artifact_declaration, sha256_digest
def _apply_engine_state(snapshot: dict[str, Any], patch: dict[str, Any]) -> None:
    """Engine-owned completion patches (not steward ``visit state patch``)."""
    state = snapshot.get("state")
    if not isinstance(state, dict):
        state = {}
        snapshot["state"] = state
    for key, value in patch.items():
        state[str(key)] = value
from foundry_cli.ledger import append_event
from foundry_cli.paths import resolve_run_uri, resolve_workspace_uri, substitute_visit_id
from foundry_cli.registry import get_node

SHAPE_PRESENT_NODE = "shape.present"
SHAPE_EXAMINE_GATE_NODE = "shape.examine.gate"
SHAPE_RECORD_NODE = "shape.record"
EXAMINE_AGENT_NAME = "shape.steward"
PRESENT_AGENT_NAME = "shape-presenter"
RECORD_AGENT_NAME = "shape-recorder"


def _accepted_agent_result(snapshot: dict[str, Any], visit_id: str, task_id: str) -> dict[str, Any] | None:
    for record in agent_requests_map(snapshot).values():
        if not isinstance(record, dict):
            continue
        if (
            record.get("visit_id") == visit_id
            and record.get("task_id") == task_id
            and record.get("status") == "accepted"
        ):
            body = record.get("accepted_result")
            return body if isinstance(body, dict) else None
    return None


def _publish_document_artifact(
    *,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    run_dir: Path,
    visit_id: str,
    artifact_id: str,
    content: str,
    foundry_bundle: Path,
) -> dict[str, Any]:
    node = get_node(flow, str(visit["node_id"]))
    artifact_decl = find_artifact_declaration(node, artifact_id)
    if artifact_decl is None:
        return {
            "ok": False,
            "code": "ARTIFACT_NOT_DECLARED",
            "message": f"Artifact {artifact_id!r} not declared on {visit['node_id']!r}",
        }

    declared_uri = substitute_visit_id(str(artifact_decl.get("uri", "")), visit_id)
    dest_path = resolve_run_uri(declared_uri, run_dir, visit_id)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(content, encoding="utf-8")
    digest = sha256_digest(dest_path)

    append_event(
        snapshot,
        event_type=EVENT_ARTIFACT_LINKED,
        visit_id=visit_id,
        node_id=str(visit["node_id"]),
        payload={
            "artifact_id": artifact_id,
            "uri": declared_uri,
            "schema": artifact_decl.get("schema") or "",
            "media_type": artifact_decl.get("media_type"),
            "digest": digest,
        },
    )
    return {"ok": True, "uri": declared_uri, "digest": digest}


def _examination_summary_markdown(result: dict[str, Any]) -> str:
    summary = str(result.get("summary") or "Examination complete.")
    lines = [summary, ""]
    criteria = result.get("draft_acceptance_criteria") or []
    if criteria:
        lines.append("## Draft acceptance criteria")
        lines.append("")
        for item in criteria:
            if isinstance(item, str) and item.strip():
                lines.append(f"- {item.strip()}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _examine_open_count_after_sync(snapshot: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
    """Sync counter from clarifying_questions; reject steward counter drift."""
    state = snapshot.get("state")
    if not isinstance(state, dict):
        return 0, None
    questions = state.get("clarifying_questions")
    if isinstance(questions, list):
        derived = derive_open_clarifying_questions_count({"clarifying_questions": questions})
        counter = state.get("open_clarifying_questions_count")
        if counter is not None and not isinstance(counter, bool) and int(counter) != derived:
            return (
                derived,
                {
                    "ok": False,
                    "code": "OPEN_QUESTIONS_MISMATCH",
                    "message": "open_clarifying_questions_count does not match clarifying_questions",
                    "derived": derived,
                    "patched": int(counter),
                },
            )
        sync_open_clarifying_questions_count(snapshot)
        return derive_open_clarifying_questions_count(state), None
    sync_open_clarifying_questions_count(snapshot)
    return derive_open_clarifying_questions_count(state), None


def run_shape_examine_complete(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    summary: str | None = None,
    with_open_questions: bool = False,
) -> dict[str, Any]:
    """Seal agent receipt and transition after accepted examination judgment.

    Policy (decision point 2): complete when open question count is zero, or when
    ``with_open_questions`` is true (gate path with unanswered clarifying questions).
    ``run advance`` calls this with ``with_open_questions=False`` only.
    """
    node_id = str(visit.get("node_id", ""))
    if node_id != SHAPE_EXAMINE_TASK_ID:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected shape.examine, got {node_id!r}"}

    visit_id = str(visit["id"])
    result = _accepted_agent_result(snapshot, visit_id, SHAPE_EXAMINE_TASK_ID)
    if result is None:
        return {
            "ok": False,
            "code": "JUDGMENT_MISSING",
            "message": "No accepted examination result for this visit",
        }

    open_count, mismatch = _examine_open_count_after_sync(snapshot)
    if mismatch is not None:
        return mismatch
    if open_count > 0 and not with_open_questions:
        return {
            "ok": False,
            "code": "OPEN_QUESTIONS_PENDING",
            "message": (
                "Examination has open clarifying questions; answer them or pass "
                "--with-open-questions to proceed to the examination gate"
            ),
            "open_clarifying_questions_count": open_count,
        }

    next_node = SHAPE_PRESENT_NODE if open_count == 0 else SHAPE_EXAMINE_GATE_NODE
    agent_draft = {
        "schema_version": "2.2.0",
        "agent": {"name": EXAMINE_AGENT_NAME, "mode": "engine"},
        "status": "completed",
        "recommended_next_state": next_node,
        "outputs": {
            "summary_markdown": _examination_summary_markdown(result),
        },
    }
    draft_path = run_dir / "receipts" / "agent.json"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(json.dumps(agent_draft, indent=2) + "\n", encoding="utf-8")

    seal_result = _seal_receipt_file(
        draft=agent_draft,
        schema_ref=AGENT_RECEIPT_SCHEMA,
        snapshot=snapshot,
        visit=visit,
        run_dir=run_dir,
        visit_id=visit_id,
        foundry_bundle=foundry_bundle,
    )
    if not seal_result.get("ok"):
        return seal_result

    return transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or "Shape examination complete",
    )


def _presentation_receipt_outputs(result: dict[str, Any], artifact_uri: str) -> dict[str, Any]:
    return {
        "summary_markdown": str(result.get("summary") or "Presentation complete."),
        "presented_ac": str(result.get("presented_ac") or ""),
        "presentation_artifact_path": artifact_uri,
    }


def seal_presentation_blocked_receipt(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    *,
    result: dict[str, Any],
    run_dir: Path,
    foundry_bundle: Path,
) -> dict[str, Any]:
    visit_id = str(visit["id"])
    blockers = result.get("blockers") or []
    agent_draft = {
        "schema_version": "2.2.0",
        "agent": {"name": PRESENT_AGENT_NAME, "mode": "shape"},
        "status": "completed",
        "recommended_next_state": SHAPE_PRESENT_NODE,
        "outputs": {
            "summary_markdown": str(result.get("summary") or "BLOCKED"),
            "blockers": list(blockers) if isinstance(blockers, list) else [],
        },
    }
    if isinstance(blockers, list) and blockers:
        agent_draft["blockers"] = [str(b) for b in blockers if str(b).strip()]
    draft_path = run_dir / "receipts" / "agent.json"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(json.dumps(agent_draft, indent=2) + "\n", encoding="utf-8")
    return _seal_receipt_file(
        draft=agent_draft,
        schema_ref=AGENT_RECEIPT_SCHEMA,
        snapshot=snapshot,
        visit=visit,
        run_dir=run_dir,
        visit_id=visit_id,
        foundry_bundle=foundry_bundle,
    )


def run_shape_present_complete(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    summary: str | None = None,
) -> dict[str, Any]:
    node_id = str(visit.get("node_id", ""))
    if node_id != SHAPE_PRESENT_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected shape.present, got {node_id!r}"}

    visit_id = str(visit["id"])
    result = _accepted_agent_result(snapshot, visit_id, SHAPE_PRESENT_TASK_ID)
    if result is None:
        return {
            "ok": False,
            "code": "JUDGMENT_MISSING",
            "message": "No accepted presentation result for this visit",
        }
    if result.get("verdict") != "PROCEED":
        return {
            "ok": False,
            "code": "PRESENTATION_BLOCKED",
            "message": "Presentation judgment is BLOCKED; resolve blockers and submit again",
        }

    presentation_md = str(result.get("presentation_markdown") or "").strip()
    if not presentation_md:
        return {
            "ok": False,
            "code": "ARTIFACT_INCOMPLETE",
            "message": "presentation_markdown is required to complete",
        }
    presented_ac = str(result.get("presented_ac") or "").strip()
    if not presented_ac:
        return {
            "ok": False,
            "code": "ARTIFACT_INCOMPLETE",
            "message": "presented_ac is required to complete",
        }
    artifact_uri = f"run:artifacts/{visit_id}/presentation.md"

    _apply_engine_state(
        snapshot,
        {
            "presented_ac": presented_ac,
            "presentation_artifact_path": artifact_uri,
        },
    )

    publish = _publish_document_artifact(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        run_dir=run_dir,
        visit_id=visit_id,
        artifact_id="presentation",
        content=presentation_md if presentation_md.endswith("\n") else presentation_md + "\n",
        foundry_bundle=foundry_bundle,
    )
    if not publish.get("ok"):
        return publish

    agent_draft = {
        "schema_version": "2.2.0",
        "agent": {"name": PRESENT_AGENT_NAME, "mode": "engine"},
        "status": "completed",
        "recommended_next_state": "shape.present.gate",
        "outputs": _presentation_receipt_outputs(result, artifact_uri),
    }
    draft_path = run_dir / "receipts" / "agent.json"
    draft_path.write_text(json.dumps(agent_draft, indent=2) + "\n", encoding="utf-8")
    seal_result = _seal_receipt_file(
        draft=agent_draft,
        schema_ref=AGENT_RECEIPT_SCHEMA,
        snapshot=snapshot,
        visit=visit,
        run_dir=run_dir,
        visit_id=visit_id,
        foundry_bundle=foundry_bundle,
    )
    if not seal_result.get("ok"):
        return seal_result

    return transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or "Shape presentation complete",
    )


def _approved_ac_digest(text: str) -> str:
    raw = text.encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def seal_record_blocked_receipt(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    *,
    result: dict[str, Any],
    run_dir: Path,
    foundry_bundle: Path,
) -> dict[str, Any]:
    visit_id = str(visit["id"])
    blockers = result.get("blockers") or []
    agent_draft = {
        "schema_version": "2.2.0",
        "agent": {"name": RECORD_AGENT_NAME, "mode": "shape"},
        "status": "completed",
        "recommended_next_state": SHAPE_RECORD_NODE,
        "outputs": {
            "summary_markdown": str(result.get("summary") or "BLOCKED"),
            "blockers": list(blockers) if isinstance(blockers, list) else [],
        },
    }
    if isinstance(blockers, list) and blockers:
        agent_draft["blockers"] = [str(b) for b in blockers if str(b).strip()]
    draft_path = run_dir / "receipts" / "agent.json"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(json.dumps(agent_draft, indent=2) + "\n", encoding="utf-8")
    return _seal_receipt_file(
        draft=agent_draft,
        schema_ref=AGENT_RECEIPT_SCHEMA,
        snapshot=snapshot,
        visit=visit,
        run_dir=run_dir,
        visit_id=visit_id,
        foundry_bundle=foundry_bundle,
    )


def _record_receipt_outputs(
    result: dict[str, Any],
    *,
    approved_ac: str,
    digest: str,
    plan_uri: str,
    plan_version: int,
) -> dict[str, Any]:
    return {
        "summary_markdown": str(result.get("summary") or "Record complete."),
        "approved_ac": approved_ac,
        "approved_ac_digest": digest,
        "plan_path": plan_uri,
        "plan_version": plan_version,
    }


def run_shape_record_complete(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    summary: str | None = None,
) -> dict[str, Any]:
    node_id = str(visit.get("node_id", ""))
    if node_id != SHAPE_RECORD_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected shape.record, got {node_id!r}"}

    visit_id = str(visit["id"])
    result = _accepted_agent_result(snapshot, visit_id, SHAPE_RECORD_TASK_ID)
    if result is None:
        return {
            "ok": False,
            "code": "JUDGMENT_MISSING",
            "message": "No accepted record result for this visit",
        }
    if result.get("verdict") != "PROCEED":
        return {
            "ok": False,
            "code": "RECORD_BLOCKED",
            "message": "Record judgment is BLOCKED; resolve blockers and submit again",
        }

    plan_md = str(result.get("plan_markdown") or "").strip()
    if not plan_md:
        return {
            "ok": False,
            "code": "ARTIFACT_INCOMPLETE",
            "message": "plan_markdown is required to complete",
        }
    approved_ac = str(result.get("approved_ac") or "").strip()
    if not approved_ac:
        return {
            "ok": False,
            "code": "ARTIFACT_INCOMPLETE",
            "message": "approved_ac is required to complete",
        }

    state = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else {}
    prior_version = state.get("approved_ac_version")
    if isinstance(prior_version, bool) or prior_version is None:
        plan_version = 1
    else:
        plan_version = int(prior_version) + 1

    plan_uri = f"run:artifacts/{visit_id}/plan.md"
    digest = _approved_ac_digest(approved_ac)

    _apply_engine_state(
        snapshot,
        {
            "approved_ac": approved_ac,
            "approved_ac_version": plan_version,
            "approved_ac_digest": digest,
            "plan_path": plan_uri,
            "plan_version": plan_version,
        },
    )

    publish = _publish_document_artifact(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        run_dir=run_dir,
        visit_id=visit_id,
        artifact_id="plan",
        content=plan_md if plan_md.endswith("\n") else plan_md + "\n",
        foundry_bundle=foundry_bundle,
    )
    if not publish.get("ok"):
        return publish

    workspace_plan = resolve_workspace_uri("workspace:plan.md", workspace)
    workspace_plan.parent.mkdir(parents=True, exist_ok=True)
    workspace_plan.write_text(plan_md, encoding="utf-8")

    agent_draft = {
        "schema_version": "2.2.0",
        "agent": {"name": RECORD_AGENT_NAME, "mode": "engine"},
        "status": "completed",
        "recommended_next_state": "shape.record.gate",
        "outputs": _record_receipt_outputs(
            result,
            approved_ac=approved_ac,
            digest=digest,
            plan_uri=plan_uri,
            plan_version=plan_version,
        ),
    }
    draft_path = run_dir / "receipts" / "agent.json"
    draft_path.write_text(json.dumps(agent_draft, indent=2) + "\n", encoding="utf-8")
    seal_result = _seal_receipt_file(
        draft=agent_draft,
        schema_ref=AGENT_RECEIPT_SCHEMA,
        snapshot=snapshot,
        visit=visit,
        run_dir=run_dir,
        visit_id=visit_id,
        foundry_bundle=foundry_bundle,
    )
    if not seal_result.get("ok"):
        return seal_result

    return transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or "Shape record complete",
    )
