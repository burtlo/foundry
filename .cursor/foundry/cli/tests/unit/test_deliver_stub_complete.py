"""End-to-end run completion through deliver.stub (stub execute and verify)."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.run_service import get_run
from tests.unit.implementation_flow_helpers import advance_stub_run_to_completion, stub_record_gate_run

pytestmark = pytest.mark.usefixtures("stub_implementation_execute")


def test_run_completes_at_deliver_stub_with_handoff(tmp_path: Path) -> None:
    run = stub_record_gate_run(tmp_path, verify_review=True)
    assert run.snapshot is not None
    snapshot = advance_stub_run_to_completion(run.workspace, run.run_id, snapshot=run.snapshot)

    assert snapshot.get("status") == "completed"
    state = snapshot.get("state") or {}
    assert isinstance(state.get("deliver_handoff_message"), str)
    assert "ready to hand off" in state["deliver_handoff_message"].lower()

    status = get_run(run.workspace, run_id=run.run_id)
    assert status.get("ok") is True
    assert status.get("handoff_message")
