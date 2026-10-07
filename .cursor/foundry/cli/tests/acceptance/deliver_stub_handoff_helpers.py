"""Arrange/assert helpers for deliver.stub handoff acceptance coverage."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.run_service import get_run
from tests.unit.constants import FIXTURE_PORCELAIN_RECORD_GATE
from tests.unit.implementation_flow_helpers import (
    advance_snapshot_to_execute_commit,
    advance_stub_run_to_completion,
    authorize_execute_start,
    enable_verify_review,
    workspace_with_run_fixture,
)


def assert_full_path_reaches_deliver_stub_with_handoff(tmp_path: Path) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    authorize_execute_start(workspace, run_id)
    enable_verify_review(workspace, run_id)
    snapshot = advance_snapshot_to_execute_commit(workspace, run_id)
    snapshot = advance_stub_run_to_completion(workspace, run_id, snapshot=snapshot)

    assert snapshot.get("status") == "completed"
    state = snapshot.get("state") or {}
    assert isinstance(state.get("deliver_handoff_message"), str)
    assert "ready to hand off" in state["deliver_handoff_message"].lower()

    status = get_run(workspace, run_id=run_id)
    assert status.get("ok") is True
    assert status.get("handoff_message")
