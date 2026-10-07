"""Host auto-advance daemon."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.agent.adapter import StubAgentAdapter
from foundry_cli.host.auto_advance import AutoAdvanceLoop, should_auto_advance_snapshot
from foundry_cli.host.auto_advance_status import read_auto_advance_status
from foundry_cli.ledger import filter_events
from foundry_cli.run_store import get_revision, load_snapshot, save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import intake_open_run, shape_test_workspace, valid_examination_result

BUNDLE = FOUNDRY_ROOT


def test_should_auto_advance_agent_wait() -> None:
    snapshot = {"status": "running", "wait": {"kind": "agent", "request_ref": "ar_x"}}
    assert should_auto_advance_snapshot(snapshot) is True


def test_should_not_auto_advance_user_gate() -> None:
    snapshot = {"status": "running", "wait": {"kind": "decision"}}
    assert should_auto_advance_snapshot(snapshot) is False


def test_should_not_auto_advance_paused() -> None:
    snapshot = {"status": "paused", "wait": None}
    assert should_auto_advance_snapshot(snapshot) is False


def test_should_auto_advance_when_no_wait() -> None:
    snapshot = {"status": "running", "wait": None}
    assert should_auto_advance_snapshot(snapshot) is True


def test_should_not_auto_advance_user_input() -> None:
    snapshot = {"status": "running", "wait": {"kind": "user_input"}}
    assert should_auto_advance_snapshot(snapshot) is False


def test_tick_advances_agent_wait_with_stub_adapter(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, flow = intake_open_run(workspace, work_prompt="Auto advance me")
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert snapshot.get("wait", {}).get("kind") == "agent"
    save_snapshot(run_dir, snapshot)

    loop = AutoAdvanceLoop(
        workspace=workspace,
        bundle=BUNDLE,
        agent_adapter=StubAgentAdapter(),
        interval_seconds=0.1,
        step_budget=8,
    )
    progressed = loop.tick_once()
    assert progressed == 1

    reloaded = load_snapshot(run_dir)
    accepted = filter_events(reloaded, types=["agent.result.accepted"])
    assert len(accepted) >= 1
    assert reloaded.get("state", {}).get("draft_ac")
    wait = reloaded.get("wait")
    assert isinstance(wait, dict)
    assert wait.get("kind") in {"decision", "user_input", "agent", "operator"}

    status = read_auto_advance_status(workspace)
    assert status is not None
    assert status.get("runs_advanced") == 1
    assert status.get("last_tick_at")
