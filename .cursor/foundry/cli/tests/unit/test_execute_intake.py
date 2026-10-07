"""Integration tests for execute.intake through execute.intake.gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.engine.advance import advance_run
from foundry_cli.run_store import load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.git_workspace import ensure_clean_git_workspace
from tests.unit.implementation_flow_helpers import stub_record_gate_run
from tests.unit.snapshot_helpers import find_visit

pytestmark = pytest.mark.usefixtures("stub_implementation_execute")


def test_advance_from_intake_passes_gate_and_records_branch(tmp_path: Path) -> None:
    run = stub_record_gate_run(tmp_path, advance_to=None)
    ensure_clean_git_workspace(run.workspace)
    assert run.snapshot is None
    snapshot = load_snapshot(run.run_dir)
    result = advance_run(
        snapshot,
        run.flow,
        workspace=run.workspace,
        foundry_bundle=FOUNDRY_ROOT,
        run_dir=run.run_dir,
        step_budget=12,
    )
    assert result["reason"] != "execution_error"
    assert snapshot.get("status") == "running"
    active = snapshot.get("active_visit") or {}
    assert active.get("node_id") in {"execute.branch", "execute.plan", "execute.build"}
    state = snapshot.get("state") or {}
    assert state.get("feature_branch", "").startswith("foundry/")
    assert state.get("execution_graph_id")

    gate_visit = find_visit(snapshot, "execute.intake.gate")
    assert gate_visit is not None
    assert gate_visit.get("decision") == "pass"

    if active.get("node_id") == "execute.build":
        wait = snapshot.get("wait")
        assert wait is None
