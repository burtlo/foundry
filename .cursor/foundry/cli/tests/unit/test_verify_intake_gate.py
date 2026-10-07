"""Integration tests for verify.intake.gate after stub execute."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import FOUNDRY_ROOT
from tests.unit.implementation_flow_helpers import stub_record_gate_run
from tests.unit.snapshot_helpers import advance_run_steps, find_visit, resolve_gate_at_node

pytestmark = pytest.mark.usefixtures("stub_implementation_execute")


def test_verify_intake_gate_passes_with_intake_receipt(tmp_path: Path) -> None:
    run = stub_record_gate_run(tmp_path)
    assert run.snapshot is not None
    snapshot = advance_run_steps(
        run.snapshot,
        run.flow,
        workspace=run.workspace,
        foundry_bundle=FOUNDRY_ROOT,
        run_dir=run.run_dir,
        max_steps=24,
        stop_when_visit="verify.intake.gate",
    )
    intake_gate = find_visit(snapshot, "verify.intake.gate")
    assert intake_gate is not None
    gate = resolve_gate_at_node(snapshot, run.flow, run.run_dir, "verify.intake.gate", visit=intake_gate)
    assert gate.get("decision") == "pass"
