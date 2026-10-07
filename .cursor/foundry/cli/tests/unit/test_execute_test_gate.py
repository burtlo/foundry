"""Integration tests for execute.test.gate routing (stub execute build/test)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.implementation_flow_helpers import stub_record_gate_run
from tests.unit.snapshot_helpers import find_visit

pytestmark = pytest.mark.usefixtures("stub_implementation_execute")


def test_stub_pass_advances_to_execute_commit(tmp_path: Path) -> None:
    run = stub_record_gate_run(tmp_path, advance_to="execute.commit")
    assert run.snapshot is not None
    snapshot = run.snapshot
    assert snapshot.get("status") == "running"
    active = snapshot.get("active_visit") or {}
    assert active.get("node_id") == "execute.commit"
    test_gate = find_visit(snapshot, "execute.test.gate")
    assert test_gate is not None
    assert test_gate.get("decision") == "pass"


def test_failed_test_routes_to_repair_limit_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_TEST_EXIT_CODE", "1")
    run = stub_record_gate_run(tmp_path, advance_to="execute.build")
    assert run.snapshot is not None
    snapshot = run.snapshot
    assert snapshot.get("status") == "running"
    active = snapshot.get("active_visit") or {}
    assert active.get("node_id") == "execute.build"
    repair_gate = find_visit(snapshot, "execute.repair.limit.gate")
    assert repair_gate is not None
    assert repair_gate.get("decision") == "proceed"
    test_gate = find_visit(snapshot, "execute.test.gate")
    assert test_gate is not None
    assert test_gate.get("decision") == "repair"
