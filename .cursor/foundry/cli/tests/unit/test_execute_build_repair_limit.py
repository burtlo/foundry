"""execute.build/test stub path and execute.repair.limit.gate routing."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.engine.gates import resolve_engine_gate_decision
from foundry_cli.engine.hooks import run_hook
from foundry_cli.engine.routing import evaluate_when_expression
from foundry_cli.registry import load_registry
from foundry_cli.run_store import load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import FIXTURE_PORCELAIN_RECORD_GATE
from tests.unit.implementation_flow_helpers import (
    advance_snapshot_through_stub_execute,
    authorize_execute_start,
    workspace_with_run_fixture,
)

BUNDLE = FOUNDRY_ROOT


@pytest.fixture(autouse=True)
def _stub_execute_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.unit.stub_execute_env import configure_stub_execute_commands

    configure_stub_execute_commands(monkeypatch)


def test_execute_build_test_pass_reaches_commit(tmp_path: Path) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    authorize_execute_start(workspace, run_id)
    snapshot = advance_snapshot_through_stub_execute(workspace, run_id, stop_at="execute.commit")
    assert snapshot.get("status") == "running"
    active = snapshot.get("active_visit") or {}
    assert active.get("node_id") == "execute.commit"
    test_gate = next(
        (v for v in snapshot.get("visits", []) if v.get("node_id") == "execute.test.gate"),
        None,
    )
    assert test_gate is not None
    assert test_gate.get("decision") == "pass"


def test_execute_test_fail_routes_repair_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_TEST_EXIT_CODE", "1")
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    authorize_execute_start(workspace, run_id)
    snapshot = advance_snapshot_through_stub_execute(workspace, run_id, stop_at="execute.build")
    assert snapshot.get("status") == "running"
    active = snapshot.get("active_visit") or {}
    assert active.get("node_id") == "execute.build"
    repair_gate = next(
        (v for v in snapshot.get("visits", []) if v.get("node_id") == "execute.repair.limit.gate"),
        None,
    )
    assert repair_gate is not None
    assert repair_gate.get("decision") == "proceed"
    test_gate = next(
        (v for v in snapshot.get("visits", []) if v.get("node_id") == "execute.test.gate"),
        None,
    )
    assert test_gate is not None
    assert test_gate.get("decision") == "repair"


def test_repair_within_limit_expression_boundary() -> None:
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


def test_repair_limit_gate_resolver_proceeds_within_limit(tmp_path: Path) -> None:
    _, flow = load_registry(BUNDLE)
    snapshot = {
        "config": {"limits": {"repair": 2}},
        "ledger": [
            {
                "seq": 1,
                "type": "connection.taken",
                "payload": {"loop": "repair"},
            }
        ],
    }
    visit = {"id": "v-rl2", "node_id": "execute.repair.limit.gate", "kind": "gate"}
    from foundry_cli.engine.gates import gate_examine_check_ids
    from tests.unit.helpers import seed_gate_examine_passes

    seed_gate_examine_passes(snapshot, visit, gate_examine_check_ids("execute.repair.limit.gate"))
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=tmp_path)
    assert result["ok"] is True
    assert result["decision"] == "proceed"


def test_repair_limit_gate_on_examine_escalates_when_over_limit(
    tmp_path: Path,
) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    _, flow = load_registry(BUNDLE)
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
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is False
    assert result.get("action") == "escalate"
