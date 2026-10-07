"""Boundary audit rows for execute-verify-deliver path (REL-015 / G7)."""

from __future__ import annotations

import pytest

from foundry_cli.engine.node_capability import audit_rows
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT

_KEY_ADVANCE_LABELS: dict[str, str] = {
    "execute.branch": "Git/mechanical advance class (`run_execute_branch_complete`)",
    "execute.plan": "Agent task binding (`execute.plan`); `dispatch_task_bound_advance` after submit",
    "verify.acceptance": (
        "Agent task binding (`verify.acceptance`); "
        "`dispatch_task_bound_advance` after submit"
    ),
    "execute.intake.gate": (
        "Engine gate; `resolve_engine_gate` on advance "
        "(host routes after decision)"
    ),
}


@pytest.fixture(scope="module")
def audit_table() -> list[dict[str, str]]:
    _, flow = load_registry(BUNDLE)
    return audit_rows(flow, BUNDLE)


def test_audit_rows_cover_execute_verify_deliver_path(audit_table: list[dict[str, str]]) -> None:
    node_ids = [row["node_id"] for row in audit_table]
    assert node_ids[0] == "execute.start"
    assert node_ids[-1] == "deliver.stub"
    assert "verify.acceptance" in node_ids


@pytest.mark.parametrize("node_id,expected_label", list(_KEY_ADVANCE_LABELS.items()))
def test_audit_advance_behavior_labels(
    audit_table: list[dict[str, str]],
    node_id: str,
    expected_label: str,
) -> None:
    by_id = {row["node_id"]: row for row in audit_table}
    row = by_id[node_id]
    assert row["advance_behavior"] == expected_label


def test_audit_no_unsupported_on_execute_verify_path(audit_table: list[dict[str, str]]) -> None:
    statuses = {row["node_id"]: row["status"] for row in audit_table}
    assert all(status != "unsupported" for status in statuses.values())
