"""Operator history projection (P17) — pure projection and host read."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.engine.blocked_intake import BLOCKED_INTAKE_STATUS_CODE
from foundry_cli.engine.run_status_reason import set_status_reason
from foundry_cli.host.handlers import HostHandlers
from foundry_cli.operator_history import project_operator_history
from foundry_cli.operator_history_service import build_operator_history
from foundry_cli.registry import load_registry
from foundry_cli.run_labels import node_step_title
from foundry_cli.run_store import save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import shape_test_workspace

BUNDLE = FOUNDRY_ROOT

INTAKE_TEXT = "Add rate limiting to the public API"
EXAM_SUMMARY = "Examination found one open question about API versioning."
QUESTION_TEXT = "Which API version should rate limits apply to?"
ANSWER_TEXT = "REST v2 only"
DECISION_LINE = "**shape.present.gate:** accept"
PRESENTATION_BODY = "# Plan presentation\n\nShip rate limits on REST v2."


def _fixture_snapshot_and_run_dir(tmp_path: Path) -> tuple[Path, dict, dict]:
    workspace = shape_test_workspace(tmp_path)
    _, flow = load_registry(BUNDLE)
    visit_present = "v-present"
    visit_gate = "v-gate"
    run_dir = workspace / ".foundry" / "runs" / "adv-op-hist"
    artifact_dir = run_dir / "artifacts" / visit_present
    artifact_dir.mkdir(parents=True)
    presentation_path = artifact_dir / "presentation.md"
    presentation_path.write_text(PRESENTATION_BODY, encoding="utf-8")

    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "adv-op-hist",
        "flow_id": "implementation",
        "status": "running",
        "revision": 4,
        "config": {"workspace": str(workspace), "shape": {"work_prompt": INTAKE_TEXT}},
        "state": {
            "ticket": {"raw_input": INTAKE_TEXT},
            "clarifying_questions": [
                {
                    "id": "q1",
                    "text": QUESTION_TEXT,
                    "why_needed": "Version scope",
                    "status": "resolved",
                }
            ],
            "clarifying_answers": {"q1": ANSWER_TEXT},
            "presentation_artifact_path": f"run:artifacts/{visit_present}/presentation.md",
            "presented_ac": "- Rate limits apply to REST v2",
        },
        "agent_requests": {
            "req-examine": {
                "visit_id": "v-examine",
                "task_id": "shape.examine",
                "status": "accepted",
                "accepted_result": {
                    "summary": EXAM_SUMMARY,
                    "draft_acceptance_criteria": ["Rate limits on REST v2"],
                    "assumptions": ["Existing auth is unchanged"],
                    "questions": [],
                    "decisions": [],
                },
            }
        },
        "ledger": [
            {
                "seq": 1,
                "type": "gate.resolved",
                "visit_id": visit_gate,
                "node_id": "shape.present.gate",
                "payload": {"decision": "accept", "decider": "user"},
            }
        ],
        "active_visit": {
            "id": visit_gate,
            "node_id": "shape.present.gate",
            "kind": "gate",
            "lifecycle": "opened",
        },
        "wait": {
            "kind": "decision",
            "visit_id": visit_gate,
            "summary": "Approve plan presentation",
        },
    }
    save_snapshot(run_dir, snapshot)
    return run_dir, snapshot, flow


def test_operator_history_projection_order_and_excludes_steward_headings(tmp_path: Path) -> None:
    run_dir, snapshot, flow = _fixture_snapshot_and_run_dir(tmp_path)
    projection = project_operator_history(snapshot, flow, run_dir=run_dir)
    markdown = projection["markdown"]
    assert isinstance(markdown, str)

    for forbidden in ("## Position", "## Examination", "## Judgment", "## Allow", "## Operations"):
        assert forbidden not in markdown

    positions = [
        markdown.index(INTAKE_TEXT),
        markdown.index(EXAM_SUMMARY),
        markdown.index(QUESTION_TEXT),
        markdown.index("*(q1)*"),
        markdown.index(ANSWER_TEXT),
        markdown.index(DECISION_LINE),
        markdown.index(PRESENTATION_BODY.splitlines()[0]),
    ]
    assert positions == sorted(positions)

    kinds = [section["kind"] for section in projection["sections"]]
    assert kinds == [
        "intake",
        "model_response",
        "questions",
        "decisions",
        "current_step",
        "parked",
    ]

    parked_section = projection["sections"][-1]
    assert parked_section.get("heading") == "Approval"
    assert "node=shape.present.gate" in parked_section["markdown"]
    assert "Approve plan presentation" in parked_section["markdown"]
    assert "\n## Approval\n\nstep=" in markdown
    assert markdown.rstrip().endswith("Approve plan presentation")
    assert "foundry decide" not in markdown


def test_operator_history_omits_open_clarifying_questions(tmp_path: Path) -> None:
    run_dir, snapshot, flow = _fixture_snapshot_and_run_dir(tmp_path)
    state = snapshot["state"]
    state["clarifying_questions"] = [
        {
            "id": "q-open",
            "text": "Still waiting on this one?",
            "status": "open",
        },
        {
            "id": "q1",
            "text": QUESTION_TEXT,
            "status": "resolved",
        },
    ]
    projection = project_operator_history(snapshot, flow, run_dir=run_dir)
    markdown = projection["markdown"]
    assert QUESTION_TEXT in markdown
    assert "Still waiting on this one?" not in markdown
    question_kinds = [s for s in projection["sections"] if s.get("kind") == "questions"]
    assert len(question_kinds) == 1
    assert "Still waiting" not in question_kinds[0]["markdown"]


def test_build_operator_history_service_markdown(tmp_path: Path) -> None:
    run_dir, snapshot, _flow = _fixture_snapshot_and_run_dir(tmp_path)
    workspace = run_dir.parent.parent.parent
    result = build_operator_history(
        workspace,
        BUNDLE,
        run_dir=run_dir,
        output_format="markdown",
    )
    assert result.get("ok") is True
    assert result.get("run_id") == snapshot.get("run_id")
    markdown = result.get("markdown")
    assert isinstance(markdown, str) and INTAKE_TEXT in markdown
    assert isinstance(result.get("sections"), list)


def _write_assessment(run_dir: Path, findings: list[str]) -> None:
    lines = [
        "# Intake assessment",
        "",
        "**Verdict:** BLOCKED",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {item}" for item in findings)
    lines.append("")
    receipts = run_dir / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    (receipts / "assessment.md").write_text("\n".join(lines), encoding="utf-8")


def test_operator_history_agent_wait_has_no_parked_section(tmp_path: Path) -> None:
    run_dir, snapshot, flow = _fixture_snapshot_and_run_dir(tmp_path)
    snapshot["wait"] = {
        "kind": "agent",
        "visit_id": snapshot["active_visit"]["id"],
        "summary": "Agent working",
    }
    projection = project_operator_history(snapshot, flow, run_dir=run_dir)
    kinds = [section["kind"] for section in projection["sections"]]
    assert "parked" not in kinds
    assert "\n## Approval\n\nstep=" not in projection["markdown"]
    assert "\n## Action\n\nstep=" not in projection["markdown"]


def test_operator_history_blocked_intake_parked_section(tmp_path: Path) -> None:
    run_dir, snapshot, flow = _fixture_snapshot_and_run_dir(tmp_path)
    findings = ["approved_ac missing", "plan_path missing"]
    _write_assessment(run_dir, findings)
    visit_id = "v-intake"
    snapshot["status"] = "running"
    snapshot["active_visit"] = {
        "id": visit_id,
        "node_id": "execute.intake",
        "kind": "step",
        "lifecycle": "opened",
    }
    set_status_reason(snapshot, BLOCKED_INTAKE_STATUS_CODE, message="; ".join(findings))
    snapshot["wait"] = {
        "kind": "operator",
        "visit_id": visit_id,
        "summary": "execute.intake is blocked; fix run state",
    }
    snapshot["state"] = {"ticket": {"raw_input": INTAKE_TEXT}}
    snapshot["ledger"] = []
    snapshot["agent_requests"] = {}

    projection = project_operator_history(snapshot, flow, run_dir=run_dir)
    parked = projection["sections"][-1]
    assert parked["kind"] == "parked"
    assert parked["heading"] == "Action"
    body = parked["markdown"]
    assert f"step={node_step_title('execute.intake', flow)}" in body
    assert "node=execute.intake" in body
    assert f"code={BLOCKED_INTAKE_STATUS_CODE}" in body
    assert "; ".join(findings) in body
    for item in findings:
        assert f"- {item}" in body
    markdown = projection["markdown"]
    assert markdown.endswith(body + "\n") or markdown.strip().endswith(body)
    assert "## Action" in markdown
    assert "foundry run advance" not in markdown


def test_operator_history_repair_limit_halt_parked_section(tmp_path: Path) -> None:
    """Paused halt (repair limit) ends history with P1 parked heading and body."""
    _, flow = load_registry(BUNDLE)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot: dict = {
        "run_id": "foundry-test",
        "status": "paused",
        "active_visit": {
            "id": "v-rl",
            "node_id": "execute.repair.limit.gate",
            "kind": "gate",
            "lifecycle": "opened",
        },
    }
    set_status_reason(snapshot, "REPAIR_LIMIT_EXCEEDED", message="Repair loop limit exceeded")
    projection = project_operator_history(snapshot, flow, run_dir=run_dir)
    kinds = [section["kind"] for section in projection["sections"]]
    assert kinds[-1] == "parked"
    parked = projection["sections"][-1]
    assert parked["heading"] == "Paused"
    body = parked["markdown"]
    assert f"step={node_step_title('execute.repair.limit.gate', flow)}" in body
    assert "node=execute.repair.limit.gate" in body
    assert "code=REPAIR_LIMIT_EXCEEDED" in body
    assert "Repair loop limit exceeded" in body
    markdown = projection["markdown"]
    assert "\n## Paused\n\nstep=" in markdown
    assert markdown.endswith(body + "\n") or markdown.strip().endswith(body)
    assert "foundry retry" not in markdown


def test_host_handler_run_operator_history(tmp_path: Path) -> None:
    run_dir, snapshot, _flow = _fixture_snapshot_and_run_dir(tmp_path)
    workspace = run_dir.parent.parent.parent
    handlers = HostHandlers(workspace, BUNDLE)
    result = handlers.run_operator_history(
        {"run_id": str(snapshot.get("run_id")), "format": "json"},
    )
    assert result.get("ok") is True
    sections = result.get("sections")
    assert isinstance(sections, list) and sections[0].get("kind") == "intake"
