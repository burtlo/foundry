"""Operator history projection (P17) — pure projection and host read."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.host.handlers import HostHandlers
from foundry_cli.operator_history import project_operator_history
from foundry_cli.operator_history_service import build_operator_history
from foundry_cli.registry import load_registry
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
        markdown.index(ANSWER_TEXT),
        markdown.index(DECISION_LINE),
        markdown.index(PRESENTATION_BODY.splitlines()[0]),
    ]
    assert positions == sorted(positions)

    kinds = [section["kind"] for section in projection["sections"]]
    assert kinds == ["intake", "model_response", "questions", "decisions", "current_step"]


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
