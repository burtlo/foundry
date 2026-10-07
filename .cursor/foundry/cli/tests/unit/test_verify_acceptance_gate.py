"""Integration tests for verify.acceptance.gate routing (stub acceptance)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import FOUNDRY_ROOT
from tests.unit.implementation_flow_helpers import stub_record_gate_run
from tests.unit.snapshot_helpers import advance_run_steps, find_visit

pytestmark = pytest.mark.usefixtures("stub_implementation_execute")


def test_verify_acceptance_gate_reads_findings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_VERIFY_ACCEPTANCE_DECISION", "replan")
    run = stub_record_gate_run(tmp_path, verify_review=True)
    assert run.snapshot is not None
    snapshot = advance_run_steps(
        run.snapshot,
        run.flow,
        workspace=run.workspace,
        foundry_bundle=FOUNDRY_ROOT,
        run_dir=run.run_dir,
        max_steps=80,
        stop_when_active="execute.plan",
    )
    acceptance_gate = find_visit(snapshot, "verify.acceptance.gate")
    assert acceptance_gate is not None
    assert acceptance_gate.get("decision") == "replan"
