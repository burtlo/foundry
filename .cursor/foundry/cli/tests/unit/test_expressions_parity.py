"""Parity tests for typed when-expression evaluator vs implementation-flow catalog."""

from __future__ import annotations

from typing import Any

import pytest

from foundry_cli.engine.expressions import WhenExpressionError, evaluate_when_expression
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import (
    EVENT_RECEIPT_LINKED,
    REGISTRY_AGENT_RECEIPT_SCHEMA,
    REGISTRY_INTAKE_RECEIPT_SCHEMA,
    VISIT_V001,
    VISIT_V002,
)
from tests.unit.helpers import make_visit, snapshot_with_visit_sealed

Scenario = tuple[str, dict[str, Any], dict[str, Any], bool]


def _collect_registry_when_expressions() -> list[tuple[str, str]]:
    _, flow = load_registry(FOUNDRY_ROOT)
    items: list[tuple[str, str]] = []
    checks = flow.get("checks") or {}
    for check_id, check_def in checks.items():
        if isinstance(check_def, dict) and "when" in check_def:
            items.append((f"check:{check_id}", " ".join(str(check_def["when"]).split())))
    for connection in flow.get("connections") or []:
        if isinstance(connection, dict) and "when" in connection:
            conn_id = str(connection.get("id", "connection"))
            items.append((f"connection:{conn_id}", " ".join(str(connection["when"]).split())))
    return items


def _ledger_repair_connections(count: int) -> list[dict[str, Any]]:
    return [
        {
            "seq": index + 1,
            "type": "connection.taken",
            "payload": {"loop": "repair"},
        }
        for index in range(count)
    ]


def _ledger_verify_intake_seals(count: int) -> list[dict[str, Any]]:
    return [
        {
            "seq": index + 1,
            "type": "visit.sealed",
            "node_id": "verify.intake",
            "payload": {"outcome": "completed"},
        }
        for index in range(count)
    ]


def _scenario_table() -> list[Scenario]:
    visit = make_visit(VISIT_V002)
    gate_visit = make_visit(VISIT_V001) | {"node_id": "execute.intake.gate"}
    rows: list[Scenario] = []

    for node_id in (
        "shape.intake",
        "shape.examine",
        "shape.present",
        "shape.record",
        "execute.intake",
        "execute.commit",
        "verify.intake",
        "verify.acceptance",
        "execute.build",
        "execute.test",
    ):
        expr = (
            f"history.last('visit.sealed', node_id='{node_id}') != null && "
            f"history.last('visit.sealed', node_id='{node_id}').outcome == 'completed'"
        )
        rows.append((expr, snapshot_with_visit_sealed(node_id), visit, True))
        rows.append((expr, {"ledger": []}, visit, False))

    rows.extend(
        [
            (
                "state.approved_ac_version >= 1",
                {"state": {"approved_ac_version": 1}},
                visit,
                True,
            ),
            ("state.approved_ac_version >= 1", {"state": {}}, visit, False),
            (
                "state.feature_branch != null",
                {"state": {"feature_branch": "feature/x"}},
                visit,
                True,
            ),
            ("state.feature_branch != null", {"state": {}}, visit, False),
            (
                "state.execution_graph_id != null",
                {"state": {"execution_graph_id": "g-1"}},
                visit,
                True,
            ),
            (
                "state.final_commit_sha != null",
                {"state": {"final_commit_sha": "abc"}},
                visit,
                True,
            ),
            ("config.review.enabled", {"config": {"review": {"enabled": True}}}, visit, True),
            ("config.review.enabled", {"config": {"review": {"enabled": False}}}, visit, False),
            (
                (
                    "history.last('gate.resolved', node_id='verify.acceptance.gate') != null && "
                    "history.last('gate.resolved', node_id='verify.acceptance.gate').decision == 'pass'"
                ),
                {
                    "ledger": [
                        {
                            "seq": 1,
                            "type": "gate.resolved",
                            "node_id": "verify.acceptance.gate",
                            "payload": {"decision": "pass"},
                        }
                    ]
                },
                visit,
                True,
            ),
            (
                (
                    "!config.review.enabled || (history.last('visit.sealed', node_id='verify.code_quality') "
                    "!= null && history.last('visit.sealed', node_id='verify.code_quality').outcome "
                    "in ['completed', 'not_applicable'])"
                ),
                {"config": {"review": {"enabled": False}}},
                visit,
                True,
            ),
            (
                (
                    "!config.review.enabled || (history.last('visit.sealed', node_id='verify.code_quality') "
                    "!= null && history.last('visit.sealed', node_id='verify.code_quality').outcome "
                    "in ['completed', 'not_applicable'])"
                ),
                {
                    "config": {"review": {"enabled": True}},
                    "ledger": [
                        {
                            "seq": 1,
                            "type": "visit.sealed",
                            "node_id": "verify.code_quality",
                            "payload": {"outcome": "completed"},
                        }
                    ],
                },
                visit,
                True,
            ),
            (
                (
                    "history.last('gate.resolved', node_id='verify.code_review.gate') != null && "
                    "history.last('gate.resolved', node_id='verify.code_review.gate').decision == 'accept'"
                ),
                {
                    "ledger": [
                        {
                            "seq": 1,
                            "type": "gate.resolved",
                            "node_id": "verify.code_review.gate",
                            "payload": {"decision": "accept"},
                        }
                    ]
                },
                visit,
                True,
            ),
            (
                (
                    f"history.count('{EVENT_RECEIPT_LINKED}', visit_id=visit.id, "
                    f"schema='{REGISTRY_INTAKE_RECEIPT_SCHEMA}') >= 1"
                ),
                {
                    "ledger": [
                        {
                            "seq": 1,
                            "visit_id": VISIT_V001,
                            "type": EVENT_RECEIPT_LINKED,
                            "payload": {"schema": REGISTRY_INTAKE_RECEIPT_SCHEMA},
                        }
                    ]
                },
                gate_visit,
                True,
            ),
            (
                (
                    f"history.count('{EVENT_RECEIPT_LINKED}', visit_id=visit.id, "
                    f"schema='{REGISTRY_AGENT_RECEIPT_SCHEMA}') >= 1"
                ),
                {
                    "ledger": [
                        {
                            "seq": 1,
                            "visit_id": VISIT_V001,
                            "type": EVENT_RECEIPT_LINKED,
                            "payload": {"schema": REGISTRY_AGENT_RECEIPT_SCHEMA},
                        }
                    ]
                },
                make_visit(VISIT_V001),
                True,
            ),
            (
                "history.count('connection.taken', loop='repair') <= config.limits.repair",
                {"ledger": _ledger_repair_connections(1), "config": {"limits": {"repair": 2}}},
                visit,
                True,
            ),
            (
                "history.count('connection.taken', loop='repair') <= config.limits.repair",
                {"ledger": _ledger_repair_connections(3), "config": {"limits": {"repair": 2}}},
                visit,
                False,
            ),
            (
                "history.count('visit.sealed', node_id='verify.intake') <= config.limits.reverify",
                {"ledger": _ledger_verify_intake_seals(2), "config": {"limits": {"reverify": 2}}},
                visit,
                True,
            ),
            (
                "state.open_clarifying_questions_count == 0",
                {"state": {"open_clarifying_questions_count": 0}},
                visit,
                True,
            ),
            (
                "state.open_clarifying_questions_count != 0",
                {"state": {"open_clarifying_questions_count": 2}},
                visit,
                True,
            ),
        ]
    )
    return rows


@pytest.mark.parametrize(
    ("expr", "snapshot", "visit", "expected"),
    _scenario_table(),
    ids=[f"scenario-{index}" for index in range(len(_scenario_table()))],
)
def test_when_expression_scenario(
    expr: str,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    expected: bool,
) -> None:
    assert evaluate_when_expression(snapshot, visit, expr) is expected


@pytest.mark.parametrize("source,expr", _collect_registry_when_expressions())
def test_registry_catalog_expression_is_supported(source: str, expr: str) -> None:
    """Every implementation-flow when string is accepted by the typed evaluator."""
    visit = make_visit(VISIT_V002)
    snapshot: dict[str, Any] = {"state": {}, "ledger": [], "config": {"limits": {"repair": 2, "reverify": 2}}}
    try:
        result = evaluate_when_expression(snapshot, visit, expr)
    except WhenExpressionError as exc:
        pytest.fail(f"{source} raised WhenExpressionError: {exc}")
    assert isinstance(result, bool)


def test_registry_expression_set_covers_catalog() -> None:
    catalog = {expr for _, expr in _collect_registry_when_expressions()}
    scenario_exprs = {expr for expr, *_ in _scenario_table()}
    missing = catalog - scenario_exprs
    assert not missing, f"Add parity scenarios for: {sorted(missing)}"
