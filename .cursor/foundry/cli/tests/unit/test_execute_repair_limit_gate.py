"""Tests for execute.repair.limit.gate routing and hooks."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.engine.hooks import run_hook
from foundry_cli.engine.routing import evaluate_when_expression
from foundry_cli.registry import load_registry
from foundry_cli.run_store import load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import FIXTURE_PORCELAIN_RECORD_GATE
from tests.unit.implementation_flow_helpers import workspace_with_run_fixture


def test_repair_loop_connection_count_respects_config_limit() -> None:
    expr = "history.count('connection.taken', loop='repair') <= config.limits.repair"
    snapshot = {
        "config": {"limits": {"repair": 1}},
        "ledger": [
            {
                "seq": 1,
                "type": "connection.taken",
                "payload": {"loop": "repair", "connection_id": "a"},
            },
            {
                "seq": 2,
                "type": "connection.taken",
                "payload": {"loop": "repair", "connection_id": "b"},
            },
        ],
    }
    visit = {"id": "v-rl", "node_id": "execute.repair.limit.gate"}
    assert evaluate_when_expression(snapshot, visit, expr) is False
    snapshot["ledger"] = snapshot["ledger"][:1]
    assert evaluate_when_expression(snapshot, visit, expr) is True


def test_on_examine_escalates_when_repair_limit_exceeded(tmp_path: Path) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    _, flow = load_registry(FOUNDRY_ROOT)
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    snapshot.setdefault("config", {})["limits"] = {"repair": 0}
    snapshot["ledger"] = list(snapshot.get("ledger") or [])
    snapshot["ledger"].append(
        {
            "seq": len(snapshot["ledger"]) + 1,
            "type": "connection.taken",
            "visit_id": "v-prior",
            "node_id": "execute.repair.limit.gate",
            "payload": {"loop": "repair", "connection_id": "prior"},
        }
    )
    visit = {
        "id": "v-rl3",
        "node_id": "execute.repair.limit.gate",
        "kind": "gate",
        "lifecycle": "examined",
    }
    result = run_hook(
        snapshot,
        visit,
        flow,
        "on_examine",
        workspace=workspace,
        foundry_bundle=FOUNDRY_ROOT,
        run_dir=run_dir,
    )
    assert result["ok"] is False
    assert result.get("action") == "escalate"
