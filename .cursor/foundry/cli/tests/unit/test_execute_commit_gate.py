"""Integration tests for execute.commit.gate resolution after stub execute."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import FOUNDRY_ROOT
from tests.unit.implementation_flow_helpers import stub_record_gate_run
from tests.unit.snapshot_helpers import advance_run_steps, resolve_gate_at_node

pytestmark = pytest.mark.usefixtures("stub_implementation_execute")


def test_execute_commit_gate_passes_with_final_sha(tmp_path: Path) -> None:
    run = stub_record_gate_run(tmp_path)
    assert run.snapshot is not None
    snapshot = advance_run_steps(
        run.snapshot,
        run.flow,
        workspace=run.workspace,
        foundry_bundle=FOUNDRY_ROOT,
        run_dir=run.run_dir,
        max_steps=24,
        stop_when_active="execute.commit.gate",
    )
    state = snapshot.get("state") or {}
    assert state.get("final_commit_sha")
    visit = snapshot.get("active_visit") or {}
    assert visit.get("node_id") == "execute.commit.gate"
    gate = resolve_gate_at_node(snapshot, run.flow, run.run_dir, "execute.commit.gate", visit=visit)
    assert gate.get("ok") is True
    assert gate.get("decision") == "pass"
