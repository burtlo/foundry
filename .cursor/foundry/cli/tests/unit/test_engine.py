"""Unit tests for workflow engine helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.commands import _require_capability
from foundry_cli.constants import (
    CAP_ARTIFACT_PUBLISH,
    CAP_RECEIPT_LINK,
    CAP_TRANSITION,
    CAP_RUN_AGENT_SUBMIT,
    CAP_VISIT_EXAMINE_COMPLETE,
    CAP_VISIT_INTAKE_COMPLETE,
    CAP_VISIT_STATE_PATCH,
)
from foundry_cli.engine import (
    decide_gate,
    evaluate_when_expression,
    generate_run_slug,
    patch_allowed,
    seal_receipt_path,
    select_connection,
    transition_visit,
)
from foundry_cli.engine.routing import RoutingDefinitionError, WhenExpressionError, eligible_connections
from foundry_cli.ledger import count_events
from foundry_cli.registry import get_node, load_registry
from foundry_cli.state_paths import implicit_state_grant, node_scope_prefix
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import (
    APPROVED_AC_RECORDED,
    ERROR_GATE_USE_DECIDE,
    ERROR_INVALID_GATE_DECISION,
    EVENT_RECEIPT_LINKED,
    NODE_SHAPE_EXAMINE,
    NODE_SHAPE_EXAMINE_GATE,
    NODE_SHAPE_INTAKE,
    NODE_SHAPE_PRESENT,
    NODE_SHAPE_RECORD,
    OPEN_CLARIFYING_QUESTIONS_NONZERO,
    OPEN_CLARIFYING_QUESTIONS_ZERO,
    REGISTRY_AGENT_RECEIPT_SCHEMA,
    REGISTRY_INTAKE_RECEIPT_SCHEMA,
    VISIT_V001,
    VISIT_V002,
    VISIT_V003,
    VISIT_V005,
    VISIT_V006,
    VISIT_V007,
)
from tests.unit.helpers import (
    make_visit,
    prior_visit_sealed_expression,
    snapshot_with_visit_sealed,
)


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
                "visit_id": VISIT_V001,
                "type": EVENT_RECEIPT_LINKED,
                "payload": {"schema": REGISTRY_INTAKE_RECEIPT_SCHEMA},
            }
        ]
    }
    visit = make_visit(VISIT_V001)
    expr = (
        f"history.count('{EVENT_RECEIPT_LINKED}', visit_id=visit.id, "
        f"schema='{REGISTRY_INTAKE_RECEIPT_SCHEMA}') >= 1"
    )
    assert evaluate_when_expression(snapshot, visit, expr) is True
    assert count_events(
        snapshot,
        EVENT_RECEIPT_LINKED,
        visit_id=VISIT_V001,
        schema=REGISTRY_INTAKE_RECEIPT_SCHEMA,
    ) == 1


def test_patch_allowed_state_paths() -> None:
    snapshot = {"state": {}}
    _, flow = load_registry(FOUNDRY_ROOT)
    node = get_node(flow, NODE_SHAPE_INTAKE)
    patched, rejected = patch_allowed(snapshot, node, NODE_SHAPE_INTAKE, {"app_folder": "."})
    assert patched == ["app_folder"]
    assert rejected == []
    assert snapshot["state"]["app_folder"] == "."

    denied, rejected_ticket = patch_allowed(snapshot, node, NODE_SHAPE_INTAKE, {"run_slug": "x"})
    assert denied == []
    assert rejected_ticket == ["run_slug"]

    scoped_key = f"{node_scope_prefix(NODE_SHAPE_INTAKE)}notes"
    scoped_patch, scoped_rejected = patch_allowed(snapshot, node, NODE_SHAPE_INTAKE, {scoped_key: "ok"})
    assert scoped_patch == [scoped_key]
    assert scoped_rejected == []
    assert snapshot["state"][scoped_key] == "ok"
    assert implicit_state_grant(NODE_SHAPE_INTAKE) == "state.nodes.shape.intake.*"


def test_shape_intake_capability_denials() -> None:
    _, flow = load_registry(FOUNDRY_ROOT)
    node = get_node(flow, NODE_SHAPE_INTAKE)
    assert _require_capability(node, CAP_VISIT_INTAKE_COMPLETE) is None
    for cap in (CAP_ARTIFACT_PUBLISH, CAP_RECEIPT_LINK, CAP_TRANSITION):
        denied = _require_capability(node, cap)
        assert denied is not None
        assert denied.get("error", {}).get("code") == "CAPABILITY_DENIED"


def test_shape_present_capability_contract() -> None:
    from tests.unit.constants import NODE_SHAPE_PRESENT

    _, flow = load_registry(FOUNDRY_ROOT)
    node = get_node(flow, NODE_SHAPE_PRESENT)
    assert _require_capability(node, CAP_RUN_AGENT_SUBMIT) is None
    from foundry_cli.constants import CAP_VISIT_PRESENT_COMPLETE

    assert _require_capability(node, CAP_VISIT_PRESENT_COMPLETE) is None
    for cap in (
        CAP_ARTIFACT_PUBLISH,
        CAP_RECEIPT_LINK,
        CAP_TRANSITION,
        CAP_VISIT_STATE_PATCH,
        CAP_VISIT_INTAKE_COMPLETE,
    ):
        denied = _require_capability(node, cap)
        assert denied is not None
        assert denied.get("error", {}).get("code") == "CAPABILITY_DENIED"


def test_shape_record_capability_contract() -> None:
    from foundry_cli.constants import CAP_VISIT_RECORD_COMPLETE
    from tests.unit.constants import NODE_SHAPE_RECORD

    _, flow = load_registry(FOUNDRY_ROOT)
    node = get_node(flow, NODE_SHAPE_RECORD)
    assert _require_capability(node, CAP_RUN_AGENT_SUBMIT) is None
    assert _require_capability(node, CAP_VISIT_RECORD_COMPLETE) is None
    for cap in (
        CAP_ARTIFACT_PUBLISH,
        CAP_RECEIPT_LINK,
        CAP_TRANSITION,
        CAP_VISIT_STATE_PATCH,
        CAP_VISIT_INTAKE_COMPLETE,
    ):
        denied = _require_capability(node, cap)
        assert denied is not None
        assert denied.get("error", {}).get("code") == "CAPABILITY_DENIED"


def test_shape_examine_capability_contract() -> None:
    _, flow = load_registry(FOUNDRY_ROOT)
    node = get_node(flow, NODE_SHAPE_EXAMINE)
    assert _require_capability(node, CAP_RUN_AGENT_SUBMIT) is None
    assert _require_capability(node, CAP_VISIT_EXAMINE_COMPLETE) is None
    for cap in (
        CAP_ARTIFACT_PUBLISH,
        CAP_RECEIPT_LINK,
        CAP_TRANSITION,
        CAP_VISIT_STATE_PATCH,
        CAP_VISIT_INTAKE_COMPLETE,
    ):
        denied = _require_capability(node, cap)
        assert denied is not None
        assert denied.get("error", {}).get("code") == "CAPABILITY_DENIED"


def test_open_clarifying_questions_count_expressions() -> None:
    visit = make_visit(VISIT_V002)

    zero_snapshot = {"state": {"open_clarifying_questions_count": 0}}
    assert evaluate_when_expression(zero_snapshot, visit, OPEN_CLARIFYING_QUESTIONS_ZERO) is True
    assert evaluate_when_expression(zero_snapshot, visit, OPEN_CLARIFYING_QUESTIONS_NONZERO) is False

    open_snapshot = {"state": {"open_clarifying_questions_count": 2}}
    assert evaluate_when_expression(open_snapshot, visit, OPEN_CLARIFYING_QUESTIONS_ZERO) is False
    assert evaluate_when_expression(open_snapshot, visit, OPEN_CLARIFYING_QUESTIONS_NONZERO) is True


@pytest.mark.parametrize(
    ("node_id", "visit_id"),
    [
        (NODE_SHAPE_EXAMINE, VISIT_V003),
        (NODE_SHAPE_PRESENT, VISIT_V005),
        (NODE_SHAPE_RECORD, VISIT_V007),
    ],
)
def test_prior_visit_sealed_expression(node_id: str, visit_id: str) -> None:
    snapshot = snapshot_with_visit_sealed(node_id)
    visit = make_visit(visit_id)
    expr = prior_visit_sealed_expression(node_id)
    assert evaluate_when_expression(snapshot, visit, expr) is True


def test_unknown_when_expression_raises() -> None:
    visit = make_visit(VISIT_V002)
    snapshot = {"state": {}}
    with pytest.raises(WhenExpressionError):
        evaluate_when_expression(snapshot, visit, "state.unknown_flag == true")


def test_select_connection_errors_on_zero_matches() -> None:
    flow = {
        "connections": [
            {
                "id": "a-to-b",
                "from": "a",
                "to": "b",
                "on": {"outcomes": ["completed"]},
                "when": OPEN_CLARIFYING_QUESTIONS_ZERO,
            }
        ]
    }
    snapshot = {
        "state": {"open_clarifying_questions_count": 2},
        "active_visit": {"id": VISIT_V002, "node_id": "a", "lifecycle": "sealed"},
    }
    with pytest.raises(RoutingDefinitionError) as exc_info:
        select_connection(snapshot, "a", flow, visit=snapshot["active_visit"])
    assert exc_info.value.eligible_count == 0


def test_select_connection_errors_on_ambiguous_matches() -> None:
    flow = {
        "connections": [
            {"id": "a-to-b", "from": "a", "to": "b", "on": {"outcomes": ["completed"]}},
            {"id": "a-to-c", "from": "a", "to": "c", "on": {"outcomes": ["completed"]}},
        ]
    }
    snapshot = {"active_visit": {"id": VISIT_V002, "node_id": "a", "lifecycle": "sealed"}}
    with pytest.raises(RoutingDefinitionError) as exc_info:
        select_connection(snapshot, "a", flow, visit=snapshot["active_visit"])
    assert exc_info.value.eligible_count == 2


def test_seal_receipt_path_uses_schema_convention() -> None:
    assert seal_receipt_path(REGISTRY_INTAKE_RECEIPT_SCHEMA, VISIT_V001) == "run:receipts/v-001/intake-receipt.json"
    assert seal_receipt_path(REGISTRY_AGENT_RECEIPT_SCHEMA, VISIT_V002) == "run:receipts/v-002/agent-receipt.json"
    assert seal_receipt_path("registry:schemas/custom.schema.json", VISIT_V003) == "run:receipts/v-003/receipt.json"


def test_approved_ac_recorded_expression() -> None:
    visit = make_visit(VISIT_V006)

    missing_snapshot = {"state": {}}
    assert evaluate_when_expression(missing_snapshot, visit, APPROVED_AC_RECORDED) is False

    zero_snapshot = {"state": {"approved_ac_version": 0}}
    assert evaluate_when_expression(zero_snapshot, visit, APPROVED_AC_RECORDED) is False

    recorded_snapshot = {"state": {"approved_ac_version": 1}}
    assert evaluate_when_expression(recorded_snapshot, visit, APPROVED_AC_RECORDED) is True


def test_select_connection_prefers_matching_when_clause() -> None:
    flow = {
        "connections": [
            {
                "id": f"{NODE_SHAPE_EXAMINE}-to-{NODE_SHAPE_PRESENT}",
                "from": NODE_SHAPE_EXAMINE,
                "to": NODE_SHAPE_PRESENT,
                "on": {"outcomes": ["completed"]},
                "when": OPEN_CLARIFYING_QUESTIONS_ZERO,
            },
            {
                "id": f"{NODE_SHAPE_EXAMINE}-to-{NODE_SHAPE_EXAMINE_GATE}",
                "from": NODE_SHAPE_EXAMINE,
                "to": NODE_SHAPE_EXAMINE_GATE,
                "on": {"outcomes": ["completed"]},
                "when": OPEN_CLARIFYING_QUESTIONS_NONZERO,
            },
        ]
    }
    snapshot = {
        "state": {"open_clarifying_questions_count": 1},
        "active_visit": {"id": VISIT_V002, "node_id": NODE_SHAPE_EXAMINE, "lifecycle": "sealed"},
    }
    connection = select_connection(snapshot, NODE_SHAPE_EXAMINE, flow)
    assert connection is not None
    assert connection["id"] == f"{NODE_SHAPE_EXAMINE}-to-{NODE_SHAPE_EXAMINE_GATE}"


def test_select_connection_filters_by_gate_decision() -> None:
    flow = {
        "connections": [
            {
                "id": f"{NODE_SHAPE_EXAMINE_GATE}-to-{NODE_SHAPE_PRESENT}-present",
                "from": NODE_SHAPE_EXAMINE_GATE,
                "to": NODE_SHAPE_PRESENT,
                "on": {"outcomes": ["completed"], "decisions": ["accept"]},
            },
            {
                "id": f"{NODE_SHAPE_EXAMINE_GATE}-to-{NODE_SHAPE_EXAMINE}-continue",
                "from": NODE_SHAPE_EXAMINE_GATE,
                "to": NODE_SHAPE_EXAMINE,
                "on": {"outcomes": ["completed"], "decisions": ["reject"]},
            },
        ]
    }
    snapshot = {
        "active_visit": {
            "id": VISIT_V003,
            "node_id": NODE_SHAPE_EXAMINE_GATE,
            "kind": "gate",
            "lifecycle": "sealed",
            "decision": "reject",
        }
    }
    connection = select_connection(
        snapshot, NODE_SHAPE_EXAMINE_GATE, flow, visit=snapshot["active_visit"]
    )
    assert connection is not None
    assert connection["id"] == f"{NODE_SHAPE_EXAMINE_GATE}-to-{NODE_SHAPE_EXAMINE}-continue"


def test_transition_visit_rejects_gate_nodes(tmp_path) -> None:
    snapshot = {
        "status": "running",
        "active_visit": {
            "id": VISIT_V003,
            "node_id": NODE_SHAPE_EXAMINE_GATE,
            "kind": "gate",
            "lifecycle": "opened",
        },
        "ledger": [],
        "visits": [],
    }
    visit = snapshot["active_visit"]
    flow = {"nodes": [{"id": NODE_SHAPE_EXAMINE_GATE, "kind": "gate"}], "connections": []}
    result = transition_visit(
        snapshot,
        visit,
        flow,
        workspace=tmp_path,
        foundry_bundle=tmp_path,
        run_dir=tmp_path,
    )
    assert result["ok"] is False
    assert result["code"] == ERROR_GATE_USE_DECIDE


def test_decide_gate_invalid_decision(tmp_path) -> None:
    visit = {
        "id": VISIT_V003,
        "node_id": NODE_SHAPE_EXAMINE_GATE,
        "kind": "gate",
        "lifecycle": "opened",
    }
    snapshot = {
        "status": "running",
        "active_visit": visit,
        "ledger": [],
        "visits": [visit],
    }
    flow = {
        "nodes": [
            {
                "id": NODE_SHAPE_EXAMINE_GATE,
                "kind": "gate",
                "decider": "user",
                "allow": {"user": {"decide": True}},
                "produces": {"options": ["accept", "reject"]},
            }
        ],
        "connections": [],
    }
    result = decide_gate(
        snapshot,
        visit,
        flow,
        decision="present",
        workspace=tmp_path,
        foundry_bundle=tmp_path,
        run_dir=tmp_path,
    )
    assert result["ok"] is False
    assert result["code"] == ERROR_INVALID_GATE_DECISION


@pytest.mark.parametrize(
    ("decision", "expected_connection_id", "expected_to"),
    [
        ("accept", "shape.record.gate-to-execute.start-record", "execute.start"),
        ("hold", "shape.record.gate-to-shape.present-reshape_plan", "shape.present"),
    ],
)
def test_shape_record_gate_each_option_has_one_route(
    decision: str,
    expected_connection_id: str,
    expected_to: str,
) -> None:
    _, flow = load_registry(FOUNDRY_ROOT)
    visit = {
        "id": "v-007",
        "node_id": "shape.record.gate",
        "kind": "gate",
        "lifecycle": "sealed",
        "decision": decision,
    }
    snapshot = {"state": {"approved_ac_version": 1}, "active_visit": visit}
    matches = eligible_connections(
        snapshot,
        "shape.record.gate",
        flow,
        visit=visit,
    )
    assert len(matches) == 1
    assert matches[0]["id"] == expected_connection_id
    assert matches[0]["to"] == expected_to


def test_shape_record_gate_hold_decide_routes_to_present(tmp_path: Path) -> None:
    _, flow = load_registry(FOUNDRY_ROOT)
    visit = {
        "id": "v-007",
        "node_id": "shape.record.gate",
        "kind": "gate",
        "lifecycle": "opened",
        "decision": None,
    }
    snapshot = {
        "status": "running",
        "active_visit": visit,
        "visits": [visit],
        "ledger": [],
        "state": {"approved_ac_version": 1},
    }
    result = decide_gate(
        snapshot,
        visit,
        flow,
        decision="hold",
        workspace=tmp_path,
        foundry_bundle=FOUNDRY_ROOT,
        run_dir=tmp_path,
    )
    assert result["ok"] is True
    assert result["decision"] == "hold"
    assert result["next_node_id"] == "shape.present"
    assert snapshot["active_visit"]["node_id"] == "shape.present"
