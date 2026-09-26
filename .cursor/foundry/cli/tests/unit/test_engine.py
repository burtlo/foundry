"""Unit tests for workflow engine helpers."""

from __future__ import annotations

from foundry_cli.engine import evaluate_when_expression, generate_run_slug, patch_allowed, select_connection
from foundry_cli.ledger import append_event, count_events


def test_generate_run_slug_increments(tmp_path) -> None:
    runs = tmp_path / ".foundry" / "runs"
    runs.mkdir(parents=True)
    (runs / "foundry-test-0001").mkdir()
    slug = generate_run_slug(tmp_path, "foundry-test")
    assert slug == "foundry-test-0002"


def test_receipt_sealed_expression() -> None:
    snapshot = {
        "ledger": [
            {
                "seq": 1,
                "visit_id": "v-001",
                "type": "receipt.linked",
                "payload": {"schema": "registry:schemas/intake-receipt.schema.json"},
            }
        ]
    }
    visit = {"id": "v-001"}
    expr = (
        "history.count('receipt.linked', visit_id=visit.id, "
        "schema='registry:schemas/intake-receipt.schema.json') >= 1"
    )
    assert evaluate_when_expression(snapshot, visit, expr) is True
    assert count_events(
        snapshot,
        "receipt.linked",
        visit_id="v-001",
        schema="registry:schemas/intake-receipt.schema.json",
    ) == 1


def test_patch_allowed_state_paths() -> None:
    snapshot = {"state": {}}
    node = {"allow": {"state": ["ticket", "app_folder"]}}
    patched, rejected = patch_allowed(snapshot, node, "shape.intake", {"app_folder": "."})
    assert patched == ["app_folder"]
    assert rejected == []
    assert snapshot["state"]["app_folder"] == "."

    denied, rejected_ticket = patch_allowed(snapshot, node, "shape.intake", {"run_slug": "x"})
    assert denied == []
    assert rejected_ticket == ["run_slug"]


def test_open_clarifying_questions_count_expressions() -> None:
    visit = {"id": "v-002"}
    fast_lane = "state.open_clarifying_questions_count == 0"
    gate_lane = "state.open_clarifying_questions_count != 0"

    zero_snapshot = {"state": {"open_clarifying_questions_count": 0}}
    assert evaluate_when_expression(zero_snapshot, visit, fast_lane) is True
    assert evaluate_when_expression(zero_snapshot, visit, gate_lane) is False

    open_snapshot = {"state": {"open_clarifying_questions_count": 2}}
    assert evaluate_when_expression(open_snapshot, visit, fast_lane) is False
    assert evaluate_when_expression(open_snapshot, visit, gate_lane) is True


def test_prior_examine_sealed_expression() -> None:
    snapshot = {
        "ledger": [
            {
                "seq": 1,
                "type": "visit.sealed",
                "node_id": "shape.examine",
                "payload": {"outcome": "completed"},
            }
        ]
    }
    visit = {"id": "v-003"}
    expr = (
        "history.last('visit.sealed', node_id='shape.examine') != null && "
        "history.last('visit.sealed', node_id='shape.examine').outcome == 'completed'"
    )
    assert evaluate_when_expression(snapshot, visit, expr) is True


def test_select_connection_prefers_matching_when_clause() -> None:
    flow = {
        "connections": [
            {
                "id": "shape.examine-to-shape.present",
                "from": "shape.examine",
                "to": "shape.present",
                "on": {"outcomes": ["completed"]},
                "when": "state.open_clarifying_questions_count == 0",
            },
            {
                "id": "shape.examine-to-shape.examine.gate",
                "from": "shape.examine",
                "to": "shape.examine.gate",
                "on": {"outcomes": ["completed"]},
                "when": "state.open_clarifying_questions_count != 0",
            },
        ]
    }
    snapshot = {
        "state": {"open_clarifying_questions_count": 1},
        "active_visit": {"id": "v-002", "node_id": "shape.examine", "lifecycle": "sealed"},
    }
    connection = select_connection(snapshot, "shape.examine", flow)
    assert connection is not None
    assert connection["id"] == "shape.examine-to-shape.examine.gate"
