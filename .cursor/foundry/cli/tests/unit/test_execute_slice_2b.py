"""Workflow-02 slice 2B: execute.build through execute.repair.limit.gate."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.gates import resolve_engine_gate_decision
from foundry_cli.engine.hooks import run_hook
from foundry_cli.engine.routing import evaluate_when_expression
from foundry_cli.registry import load_registry
from foundry_cli.run_service import execute_start_durable
from foundry_cli.run_store import load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.execute_advance_helpers import submit_execute_plan_proceed_if_waiting
from tests.unit.git_workspace import ensure_clean_git_workspace

BUNDLE = FOUNDRY_ROOT
FIXTURE_RECORD_GATE = "porcelain-0007-v007-record-gate"
CLI = BUNDLE / "cli" / "foundry.py"


def _workspace_with_fixture(tmp_path: Path, fixture_name: str) -> tuple[Path, str]:
    src = BUNDLE / "fixtures" / "runs" / fixture_name
    snapshot = json.loads((src / "snapshot.json").read_text(encoding="utf-8"))
    run_id = str(snapshot.get("run_id") or fixture_name)
    workspace = tmp_path / "app"
    dest = workspace / ".foundry" / "runs" / run_id
    shutil.copytree(src, dest)
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
        dirs_exist_ok=True,
    )
    ensure_clean_git_workspace(workspace)
    return workspace, run_id


def _run_cli(workspace: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--json",
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
            *argv,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _authorize_execute(workspace: Path, run_id: str) -> None:
    decide = _run_cli(workspace, "gate", "decide", "--run", run_id, "--decision", "accept")
    assert decide.returncode == 0, decide.stderr + decide.stdout
    advance = _run_cli(workspace, "run", "advance", "--run", run_id)
    assert advance.returncode == 0, advance.stderr + advance.stdout
    ensure_clean_git_workspace(workspace)
    start = execute_start_durable(workspace=workspace, bundle=BUNDLE, run_id=run_id)
    assert start.get("ok") is True, start
    assert start.get("active_node_id") == "execute.intake"


def _advance_execute_entry(workspace: Path, run_id: str, *, stop_at: str = "execute.commit") -> dict:
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    for _ in range(48):
        active = snapshot.get("active_visit") or {}
        if submit_execute_plan_proceed_if_waiting(
            snapshot,
            visit=active,
            flow=flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
        ):
            continue
        if active.get("node_id") == stop_at and active.get("lifecycle") == "opened":
            if stop_at == "execute.build":
                repair_gate = next(
                    (
                        v
                        for v in snapshot.get("visits", [])
                        if v.get("node_id") == "execute.repair.limit.gate"
                    ),
                    None,
                )
                if repair_gate is None:
                    pass
                else:
                    break
            else:
                break
        outcome = advance_run(
            snapshot,
            flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
            step_budget=1,
        )
        if not outcome.get("steps_taken"):
            reason = str(outcome.get("reason") or "")
            if reason in ("execute_build_boundary", "repair_reentry_boundary"):
                continue
            break
    return snapshot


@pytest.fixture(autouse=True)
def _stub_execute_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    monkeypatch.delenv("FOUNDRY_EXECUTE_BUILD_EXIT_CODE", raising=False)
    monkeypatch.delenv("FOUNDRY_EXECUTE_TEST_EXIT_CODE", raising=False)


def test_execute_build_test_pass_reaches_commit(tmp_path: Path) -> None:
    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
    _authorize_execute(workspace, run_id)
    snapshot = _advance_execute_entry(workspace, run_id)
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
    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
    _authorize_execute(workspace, run_id)
    snapshot = _advance_execute_entry(workspace, run_id, stop_at="execute.build")
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
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=tmp_path)
    assert result["ok"] is True
    assert result["decision"] == "proceed"


def test_repair_limit_gate_on_examine_escalates_when_over_limit(
    tmp_path: Path,
) -> None:
    workspace, run_id = _workspace_with_fixture(tmp_path, FIXTURE_RECORD_GATE)
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
