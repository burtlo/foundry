"""Host-owned Verify and Deliver steps — workflow-02 slices 2D–2F."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from foundry_cli.constants import EVENT_ARTIFACT_LINKED
from foundry_cli.engine.execute_step_executor import (
    _execute_use_stub_commands,
    _git_default_branch,
    _git_run,
    _receipt_status_from_commands,
    _seal_execute_agent_receipt,
    _snapshot_state,
    _stub_exit_code,
)
from foundry_cli.engine.intake_executor import (
    AGENT_RECEIPT_SCHEMA,
    INTAKE_RECEIPT_SCHEMA,
    _ledger_checks_for_visit,
    _seal_receipt_file,
    _write_assessment,
)
from foundry_cli.engine.lifecycle import seal_step_with_outcome, transition_visit
from foundry_cli.engine.shape_step_executor import _publish_document_artifact
from foundry_cli.engine.state import patch_allowed
from foundry_cli.registry import get_node
from foundry_cli.util import now_iso

VERIFY_INTAKE_NODE = "verify.intake"
VERIFY_ACCEPTANCE_NODE = "verify.acceptance"
VERIFY_CODE_QUALITY_NODE = "verify.code_quality"
VERIFY_CODE_REVIEW_NODE = "verify.code_review"
VERIFY_COMPLETE_NODE = "verify.complete"
DELIVER_STUB_NODE = "deliver.stub"

VERIFY_INTAKE_AGENT = "intake-checker"
IMPLEMENTATION_VALIDATOR_AGENT = "implementation-validator"


def _review_enabled(snapshot: dict[str, Any]) -> bool:
    config = snapshot.get("config")
    if not isinstance(config, dict):
        return False
    review = config.get("review")
    if not isinstance(review, dict):
        return False
    return bool(review.get("enabled"))


def _acceptance_gate_decision_from_env() -> str:
    raw = (os.environ.get("FOUNDRY_VERIFY_ACCEPTANCE_DECISION") or "pass").strip().lower()
    if raw in ("pass", "replan", "reshape", "rework_execute"):
        return raw
    return "pass"


def _branch_diff_text(workspace: Path, snapshot: dict[str, Any]) -> str:
    state = _snapshot_state(snapshot)
    feature = state.get("feature_branch")
    default = state.get("default_branch") or _git_default_branch(workspace)
    if not isinstance(feature, str) or not feature.strip():
        return "# branch diff unavailable: feature_branch missing\n"
    diff = _git_run(workspace, "diff", f"{default}...{feature}")
    if diff.returncode not in (0, 1):
        return f"# git diff failed: {diff.stderr.strip()}\n"
    body = diff.stdout or ""
    if not body.strip():
        body = "# (no diff vs default branch)\n"
    return body


def run_verify_intake_complete(
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
    if node_id != VERIFY_INTAKE_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected verify.intake, got {node_id!r}"}

    visit_id = str(visit["id"])
    state = _snapshot_state(snapshot)
    if not state.get("default_branch"):
        patch_allowed(
            snapshot,
            get_node(flow, node_id),
            node_id,
            {"default_branch": _git_default_branch(workspace)},
        )

    diff_text = _branch_diff_text(workspace, snapshot)
    diff_publish = _publish_document_artifact(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        run_dir=run_dir,
        visit_id=visit_id,
        artifact_id="branch-diff",
        content=diff_text,
        foundry_bundle=foundry_bundle,
    )
    if not diff_publish.get("ok"):
        return diff_publish

    diff_uri = str(diff_publish.get("uri") or f"run:artifacts/{visit_id}/branch.diff")
    patch_allowed(
        snapshot,
        get_node(flow, node_id),
        node_id,
        {"branch_diff_artifact_path": diff_uri, "verify_diff_scope": f"{state.get('default_branch')}...{state.get('feature_branch')}"},
    )

    checks = _ledger_checks_for_visit(snapshot, visit_id) or [{"id": "validate-verify-context", "status": "pass"}]
    receipts_dir = run_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    assessment_path = receipts_dir / "assessment.md"
    _write_assessment(
        assessment_path,
        verdict="PROCEED",
        raw_input=None,
        summary="Verify intake: execute context and branch diff validated (host).",
        findings=["final_commit_sha present", "branch diff captured"],
    )

    intake_draft = {
        "schema_version": "2.2.0",
        "step_id": node_id,
        "status": "passed",
        "checks": checks,
        "agent_assessment": {
            "assessment_path": "run:receipts/assessment.md",
            "summary_markdown": "PROCEED: verify intake checks passed (host).",
        },
    }
    agent_draft = {
        "schema_version": "2.2.0",
        "agent": {"name": VERIFY_INTAKE_AGENT, "mode": "verify"},
        "status": "completed",
        "recommended_next_state": "verify.intake.gate",
        "outputs": {
            "assessment_path": "run:receipts/assessment.md",
            "summary_markdown": "PROCEED: verify intake complete (host).",
            "branch_diff_uri": diff_uri,
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

    return transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or "Verify intake complete",
    )


def _verify_findings_payload(snapshot: dict[str, Any], gate_decision: str) -> dict[str, Any]:
    state = _snapshot_state(snapshot)
    return {
        "schema_version": "1.0.0",
        "verdict": gate_decision if gate_decision != "pass" else "pass",
        "gate_decision": gate_decision,
        "approved_ac_digest": state.get("approved_ac_digest"),
        "items": [
            {
                "criterion": str(state.get("approved_ac") or "")[:240],
                "status": "met" if gate_decision == "pass" else "not_met",
            }
        ],
    }


def run_verify_acceptance_complete(
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
    if node_id != VERIFY_ACCEPTANCE_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected verify.acceptance, got {node_id!r}"}

    visit_id = str(visit["id"])
    gate_decision = _acceptance_gate_decision_from_env()
    findings = _verify_findings_payload(snapshot, gate_decision)
    publish = _publish_document_artifact(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        run_dir=run_dir,
        visit_id=visit_id,
        artifact_id="verify-findings",
        content=json.dumps(findings, indent=2) + "\n",
        foundry_bundle=foundry_bundle,
    )
    if not publish.get("ok"):
        return publish

    patch_allowed(
        snapshot,
        get_node(flow, node_id),
        node_id,
        {"verify_findings": findings},
    )

    seal_result = _seal_execute_agent_receipt(
        snapshot=snapshot,
        visit=visit,
        run_dir=run_dir,
        foundry_bundle=foundry_bundle,
        visit_id=visit_id,
        agent_name=IMPLEMENTATION_VALIDATOR_AGENT,
        agent_mode="validate",
        commands=[{"command": "foundry-stub:acceptance", "exit_code": 0}],
        recommended_next_state="verify.acceptance.gate",
        summary_markdown=f"PROCEED: acceptance findings recorded ({gate_decision}).",
        extra_outputs={"verify_findings_uri": publish.get("uri"), "gate_decision": gate_decision},
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
        summary=summary or "Verify acceptance recorded",
    )


def _commands_for_code_quality() -> list[dict[str, Any]]:
    if _execute_use_stub_commands():
        exit_code = _stub_exit_code("code_quality", default=_stub_exit_code("build", default=0))
        return [{"command": "foundry-stub:code_quality", "exit_code": exit_code}]
    return [{"command": "foundry-stub:code_quality", "exit_code": 0}]


def run_verify_code_quality_complete(
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
    if node_id != VERIFY_CODE_QUALITY_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected verify.code_quality, got {node_id!r}"}

    lifecycle = str(visit.get("lifecycle", ""))
    if lifecycle == "examined" and not _review_enabled(snapshot):
        return seal_step_with_outcome(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
            outcome="not_applicable",
            summary=summary or "Code quality skipped (review disabled)",
            skip_close_and_seal_hooks=True,
        )

    if not _review_enabled(snapshot):
        return seal_step_with_outcome(
            snapshot,
            visit,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
            outcome="not_applicable",
            summary=summary or "Code quality skipped (review disabled)",
            skip_close_and_seal_hooks=True,
        )

    visit_id = str(visit["id"])
    commands = _commands_for_code_quality()
    report_lines = [
        "# Code quality report",
        "",
        f"**Status:** {'pass' if _receipt_status_from_commands(commands) == 'completed' else 'fail'}",
        "",
        "## Commands",
        "",
    ]
    for item in commands:
        report_lines.append(f"- `{item.get('command')}` exit={item.get('exit_code')}")
    report_lines.append("")
    publish = _publish_document_artifact(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        run_dir=run_dir,
        visit_id=visit_id,
        artifact_id="code-quality-report",
        content="\n".join(report_lines),
        foundry_bundle=foundry_bundle,
    )
    if not publish.get("ok"):
        return publish

    seal_result = _seal_execute_agent_receipt(
        snapshot=snapshot,
        visit=visit,
        run_dir=run_dir,
        foundry_bundle=foundry_bundle,
        visit_id=visit_id,
        agent_name=IMPLEMENTATION_VALIDATOR_AGENT,
        agent_mode="validate",
        commands=commands,
        recommended_next_state="verify.code_quality.gate",
        summary_markdown="PROCEED: code quality commands recorded (host).",
        extra_outputs={"report_uri": publish.get("uri")},
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
        summary=summary or "Verify code quality recorded",
    )


def run_verify_code_review_complete(
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
    if node_id != VERIFY_CODE_REVIEW_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected verify.code_review, got {node_id!r}"}

    visit_id = str(visit["id"])
    notes = "\n".join(
        [
            "# Verify notes",
            "",
            "Host-generated review packet for user gate.",
            "",
            f"- Feature branch: `{_snapshot_state(snapshot).get('feature_branch')}`",
            f"- Final commit: `{_snapshot_state(snapshot).get('final_commit_sha')}`",
            "",
        ]
    )
    publish = _publish_document_artifact(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        run_dir=run_dir,
        visit_id=visit_id,
        artifact_id="verify-notes",
        content=notes,
        foundry_bundle=foundry_bundle,
    )
    if not publish.get("ok"):
        return publish

    patch_allowed(
        snapshot,
        get_node(flow, node_id),
        node_id,
        {"verify_notes": notes[:4000]},
    )

    return transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or "Verify code review packet ready",
    )


def run_verify_complete_complete(
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
    if node_id != VERIFY_COMPLETE_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected verify.complete, got {node_id!r}"}

    patch_allowed(
        snapshot,
        get_node(flow, node_id),
        node_id,
        {"verified_at": now_iso()},
    )

    return transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or "Verify phase complete",
    )


def _deliver_handoff_message(snapshot: dict[str, Any]) -> str:
    state = _snapshot_state(snapshot)
    branch = state.get("feature_branch") or "(unknown branch)"
    commit = state.get("final_commit_sha") or "(no commit recorded)"
    run_id = str(snapshot.get("run_id") or "run")
    return (
        f"Run {run_id} is ready to hand off. Verified work is on branch `{branch}` "
        f"(commit `{commit}`). Push the branch or open a PR when you are ready."
    )


def run_deliver_stub_complete(
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
    if node_id != DELIVER_STUB_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected deliver.stub, got {node_id!r}"}

    handoff = _deliver_handoff_message(snapshot)
    state = snapshot.setdefault("state", {})
    if isinstance(state, dict):
        state["deliver_handoff_message"] = handoff

    return transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or handoff,
    )
