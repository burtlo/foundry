"""Unit tests for host execute.build completion."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.execute_step_executor import (
    EXECUTE_BUILD_PARKED_VISIT_STATE_KEY,
    EXECUTE_PLAN_TO_BUILD_CONNECTION,
    run_execute_build_complete,
)
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.execute_step_fixtures import assert_execute_step_engine_owned, opened_execute_step_run

BUNDLE = FOUNDRY_ROOT
NODE_EXECUTE_BUILD = "execute.build"
REPAIR_TO_BUILD_CONNECTION = "execute.repair.limit.gate-to-execute.build-proceed"


def _opened_build_with_admission(
    tmp_path: Path,
    *,
    admission_source: str,
    repair_loop: bool = False,
) -> tuple[Path, Path, dict, dict, dict]:
    workspace, run_dir, snapshot, visit, flow = opened_execute_step_run(
        tmp_path,
        node_id=NODE_EXECUTE_BUILD,
        run_id="build-boundary",
        visit_id="v-build-boundary",
        state={
            "execution_graph_id": "build-boundary:execution-graph",
            "feature_branch": "foundry/test",
            "approved_ac": "Ship it.",
        },
    )
    ledger: list[dict] = [
        {
            "type": "visit.admitted",
            "visit_id": visit["id"],
            "node_id": NODE_EXECUTE_BUILD,
            "payload": {"source": admission_source},
        }
    ]
    if repair_loop:
        ledger.append(
            {
                "type": "connection.taken",
                "payload": {
                    "connection_id": admission_source,
                    "loop": "repair",
                },
            }
        )
    snapshot["ledger"] = ledger
    return workspace, run_dir, snapshot, visit, flow


def test_implementation_flow_execute_build_engine_owned() -> None:
    _, flow = load_registry(BUNDLE)
    assert_execute_step_engine_owned(
        flow,
        NODE_EXECUTE_BUILD,
        allow_state=["last_build_exit_code"],
    )


def test_build_complete_happy_path_stub(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    workspace, run_dir, snapshot, visit, flow = opened_execute_step_run(
        tmp_path,
        node_id=NODE_EXECUTE_BUILD,
        run_id="build-test",
        visit_id="v-build",
        state={
            "execution_graph_id": "build-test:execution-graph",
            "feature_branch": "foundry/test",
            "approved_ac": "Ship it.",
        },
    )
    result = run_execute_build_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is True
    assert result.get("next_node_id") == "execute.test"
    assert snapshot.get("state", {}).get("last_build_exit_code") == 0
    agent_path = run_dir / "receipts" / "agent.json"
    assert agent_path.is_file()
    draft = json.loads(agent_path.read_text(encoding="utf-8"))
    assert draft.get("agent", {}).get("name") == "feature-builder"
    assert draft.get("status") == "completed"
    commands = draft.get("commands") or []
    assert commands and commands[0].get("exit_code") == 0


def test_build_complete_records_failed_stub_exit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    monkeypatch.setenv("FOUNDRY_EXECUTE_BUILD_EXIT_CODE", "2")
    workspace, run_dir, snapshot, visit, flow = opened_execute_step_run(
        tmp_path,
        node_id=NODE_EXECUTE_BUILD,
        run_id="build-test",
        visit_id="v-build",
        state={
            "execution_graph_id": "build-test:execution-graph",
            "feature_branch": "foundry/test",
            "approved_ac": "Ship it.",
        },
    )
    result = run_execute_build_complete(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is False
    assert result.get("reopened") is True
    assert result.get("code") == "CHECK_FAILED"
    agent_path = run_dir / "receipts" / "agent.json"
    draft = json.loads(agent_path.read_text(encoding="utf-8"))
    assert draft.get("status") == "failed"
    assert snapshot.get("state", {}).get("last_build_exit_code") == 2


def test_execute_build_boundary_parks_after_plan_admission(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    workspace, run_dir, snapshot, visit, flow = _opened_build_with_admission(
        tmp_path,
        admission_source=EXECUTE_PLAN_TO_BUILD_CONNECTION,
    )
    first = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=1,
    )
    assert first.get("steps_taken") == 0
    assert first.get("reason") == "execute_build_boundary"
    state = snapshot.get("state") or {}
    assert state.get(EXECUTE_BUILD_PARKED_VISIT_STATE_KEY) == visit["id"]

    second = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=1,
    )
    assert second.get("steps_taken")
    assert snapshot.get("active_visit", {}).get("node_id") == "execute.test"
    assert EXECUTE_BUILD_PARKED_VISIT_STATE_KEY not in (snapshot.get("state") or {})


def test_execute_build_boundary_parks_on_repair_reentry(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    workspace, run_dir, snapshot, visit, flow = _opened_build_with_admission(
        tmp_path,
        admission_source=REPAIR_TO_BUILD_CONNECTION,
        repair_loop=True,
    )
    first = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=1,
    )
    assert first.get("steps_taken") == 0
    assert first.get("reason") == "repair_reentry_boundary"

    second = advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
        step_budget=1,
    )
    assert second.get("steps_taken")
    assert snapshot.get("active_visit", {}).get("node_id") == "execute.test"
