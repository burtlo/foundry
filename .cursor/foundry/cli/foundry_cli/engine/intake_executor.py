"""Deterministic shape.intake mechanism (no LLM on happy path)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from foundry_cli.constants import (
    EVENT_ARTIFACT_LINKED,
    EVENT_CHECK_RECORDED,
    EVENT_RECEIPT_LINKED,
)
from foundry_cli.engine.lifecycle import transition_visit
from foundry_cli.engine.receipts import (
    fill_receipt_provenance,
    find_artifact_declaration,
    schema_name_from_registry,
    seal_receipt_path,
    sha256_digest,
)
from foundry_cli.engine.state import patch_allowed
from foundry_cli.ledger import filter_events
from foundry_cli.paths import resolve_run_uri, substitute_visit_id
from foundry_cli.registry import get_node
from foundry_cli.validate import validate_payload

INTAKE_RECEIPT_SCHEMA = "registry:schemas/intake-receipt.schema.json"
AGENT_RECEIPT_SCHEMA = "registry:schemas/agent-receipt.schema.json"
TICKET_SCHEMA = "registry:schemas/ticket.schema.json"
INTAKE_AGENT_NAME = "foundry.intake"
BLOCK_REASON_MISSING_WORK_PROMPT = "WORK_PROMPT_MISSING"


def _ledger_checks_for_visit(snapshot: dict[str, Any], visit_id: str) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for event in filter_events(snapshot, types=[EVENT_CHECK_RECORDED]):
        if str(event.get("visit_id")) != visit_id:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        check_id = payload.get("check_id")
        if not check_id:
            continue
        result = str(payload.get("result", "pass"))
        status = "pass" if result == "pass" else "fail"
        entry: dict[str, Any] = {"id": str(check_id), "status": status}
        detail = payload.get("detail")
        if isinstance(detail, dict) and detail.get("errors"):
            entry["summary"] = "; ".join(str(item) for item in detail.get("errors", [])[:3])
        checks.append(entry)
    return checks


def _write_assessment(path: Path, *, verdict: str, raw_input: str | None, summary: str, findings: list[str]) -> None:
    lines = [
        "# Shape intake assessment",
        "",
        f"**Verdict:** {verdict}",
        "",
        "## Findings",
        "",
    ]
    for finding in findings:
        lines.append(f"- {finding}")
    lines.extend(["", "## Verdict summary", "", summary, ""])
    if raw_input is not None:
        lines.extend(
            [
                "## Captured input",
                "",
                "```",
                raw_input,
                "```",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _seal_receipt_file(
    *,
    draft: dict[str, Any],
    schema_ref: str,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    run_dir: Path,
    visit_id: str,
    foundry_bundle: Path,
) -> dict[str, Any]:
    sealed = fill_receipt_provenance(draft, schema_ref=schema_ref, snapshot=snapshot, visit=visit)
    schema_errors = validate_payload(sealed, schema_name_from_registry(schema_ref), foundry_bundle)
    if schema_errors:
        return {"ok": False, "code": "SCHEMA_VALIDATION_FAILED", "message": "; ".join(schema_errors)}

    sealed_uri = seal_receipt_path(schema_ref, visit_id)
    sealed_path = resolve_run_uri(sealed_uri, run_dir, visit_id)
    sealed_path.parent.mkdir(parents=True, exist_ok=True)
    sealed_path.write_text(json.dumps(sealed, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    from foundry_cli.ledger import append_event

    event = append_event(
        snapshot,
        event_type=EVENT_RECEIPT_LINKED,
        visit_id=visit_id,
        node_id=str(visit["node_id"]),
        payload={
            "receipt_id": sealed.get("receipt_id"),
            "path": sealed_uri,
            "schema": schema_ref,
        },
    )
    return {"ok": True, "receipt_id": sealed.get("receipt_id"), "path": sealed_uri, "ledger_seq": event.get("seq")}


def _publish_ticket(
    *,
    ticket: dict[str, Any],
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    run_dir: Path,
    visit_id: str,
    foundry_bundle: Path,
) -> dict[str, Any]:
    node = get_node(flow, str(visit["node_id"]))
    artifact_decl = find_artifact_declaration(node, "ticket")
    if artifact_decl is None:
        return {"ok": False, "code": "ARTIFACT_NOT_DECLARED", "message": "ticket artifact not declared"}

    schema_errors = validate_payload(ticket, schema_name_from_registry(TICKET_SCHEMA), foundry_bundle)
    if schema_errors:
        return {"ok": False, "code": "SCHEMA_VALIDATION_FAILED", "message": "; ".join(schema_errors)}

    draft_path = run_dir / "ticket.json"
    draft_path.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    declared_uri = substitute_visit_id(str(artifact_decl.get("uri", "")), visit_id)
    dest_path = resolve_run_uri(declared_uri, run_dir, visit_id)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(draft_path, dest_path)
    digest = sha256_digest(dest_path)

    from foundry_cli.ledger import append_event

    event = append_event(
        snapshot,
        event_type=EVENT_ARTIFACT_LINKED,
        visit_id=visit_id,
        node_id=str(visit["node_id"]),
        payload={
            "artifact_id": "ticket",
            "uri": declared_uri,
            "schema": TICKET_SCHEMA,
            "media_type": artifact_decl.get("media_type"),
            "digest": digest,
        },
    )
    state = snapshot.setdefault("state", {})
    if isinstance(state, dict):
        state["ticket"] = ticket

    return {"ok": True, "uri": declared_uri, "ledger_seq": event.get("seq")}


def run_shape_intake_complete(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    work_prompt: str | None,
    source_type: str = "chat",
    source_ref: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """Execute deterministic intake: ticket, receipts, optional transition."""
    node_id = str(visit.get("node_id", ""))
    if node_id != "shape.intake":
        return {"ok": False, "code": "WRONG_NODE", "message": f"visit intake complete requires shape.intake, got {node_id!r}"}

    visit_id = str(visit["id"])
    state = snapshot.setdefault("state", {})
    if not isinstance(state, dict):
        state = {}
        snapshot["state"] = state

    if state.get("app_folder") in (None, ""):
        patch_allowed(snapshot, get_node(flow, node_id), node_id, {"app_folder": str(workspace)})

    prompt = (work_prompt or "").strip()
    receipts_dir = run_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    assessment_path = receipts_dir / "assessment.md"
    checks = _ledger_checks_for_visit(snapshot, visit_id)
    if not checks:
        checks = [{"id": "validate-manifest", "status": "pass"}]

    if not prompt:
        _write_assessment(
            assessment_path,
            verdict="BLOCKED",
            raw_input=None,
            summary="Intake blocked: work request missing.",
            findings=[f"Structured reason: {BLOCK_REASON_MISSING_WORK_PROMPT}"],
        )
        intake_draft = {
            "schema_version": "2.2.0",
            "step_id": node_id,
            "status": "blocked",
            "checks": checks,
            "agent_assessment": {
                "assessment_path": "run:receipts/assessment.md",
                "summary_markdown": "BLOCKED: work request missing.",
                "blocked_reason": BLOCK_REASON_MISSING_WORK_PROMPT,
            },
        }
        agent_draft = {
            "schema_version": "2.2.0",
            "agent": {"name": INTAKE_AGENT_NAME, "mode": "engine"},
            "status": "completed",
            "recommended_next_state": node_id,
            "outputs": {
                "assessment_path": "run:receipts/assessment.md",
                "summary_markdown": "BLOCKED: work request missing.",
                "block_reason": BLOCK_REASON_MISSING_WORK_PROMPT,
            },
        }
        for schema_ref, draft, file_name in (
            (INTAKE_RECEIPT_SCHEMA, intake_draft, "intake.json"),
            (AGENT_RECEIPT_SCHEMA, agent_draft, "agent.json"),
        ):
            draft_path = receipts_dir / file_name
            draft_path.write_text(json.dumps(draft, indent=2) + "\n", encoding="utf-8")
            seal_result = _seal_receipt_file(
                draft=draft,
                schema_ref=schema_ref,
                snapshot=snapshot,
                visit=visit,
                run_dir=run_dir,
                visit_id=visit_id,
                foundry_bundle=foundry_bundle,
            )
            if not seal_result.get("ok"):
                return seal_result

        return {
            "ok": True,
            "intake_status": "blocked",
            "block_reason": BLOCK_REASON_MISSING_WORK_PROMPT,
            "transitioned": False,
            "visit_id": visit_id,
            "node_id": node_id,
        }

    ticket = {
        "schema_version": "2.2.0",
        "raw_input": prompt,
        "normalized_translation": None,
        "source_type": source_type,
        "source_ref": source_ref,
        "issue_key": None,
    }
    _write_assessment(
        assessment_path,
        verdict="PROCEED",
        raw_input=prompt,
        summary="Intake complete (deterministic capture).",
        findings=["Work request captured verbatim.", "Application manifest validated on admit."],
    )
    intake_draft = {
        "schema_version": "2.2.0",
        "step_id": node_id,
        "status": "passed",
        "checks": checks,
        "agent_assessment": {
            "assessment_path": "run:receipts/assessment.md",
            "summary_markdown": "PROCEED: work request captured.",
        },
    }
    agent_draft = {
        "schema_version": "2.2.0",
        "agent": {"name": INTAKE_AGENT_NAME, "mode": "engine"},
        "status": "completed",
        "recommended_next_state": "shape.examine",
        "outputs": {
            "assessment_path": "run:receipts/assessment.md",
            "summary_markdown": "PROCEED: work request captured.",
        },
    }

    publish_result = _publish_ticket(
        ticket=ticket,
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        run_dir=run_dir,
        visit_id=visit_id,
        foundry_bundle=foundry_bundle,
    )
    if not publish_result.get("ok"):
        return publish_result

    for schema_ref, draft, file_name in (
        (INTAKE_RECEIPT_SCHEMA, intake_draft, "intake.json"),
        (AGENT_RECEIPT_SCHEMA, agent_draft, "agent.json"),
    ):
        draft_path = receipts_dir / file_name
        draft_path.write_text(json.dumps(draft, indent=2) + "\n", encoding="utf-8")
        seal_result = _seal_receipt_file(
            draft=draft,
            schema_ref=schema_ref,
            snapshot=snapshot,
            visit=visit,
            run_dir=run_dir,
            visit_id=visit_id,
            foundry_bundle=foundry_bundle,
        )
        if not seal_result.get("ok"):
            return seal_result

    transition_result = transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or "Shape intake complete",
    )
    if not transition_result.get("ok"):
        return transition_result

    return {
        "ok": True,
        "intake_status": "passed",
        "transitioned": True,
        **transition_result,
    }
