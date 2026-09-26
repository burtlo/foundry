"""Step definitions for shape_examine.feature."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from pytest_bdd import given, parsers, then

from tests.conftest import FOUNDRY_ROOT

FIXTURES_ROOT = FOUNDRY_ROOT / "fixtures" / "runs"


@given(parsers.parse('run fixture "{fixture_name}" in temporary workspace'))
def run_fixture_in_temp_workspace(acceptance, fixture_name: str, tmp_path) -> None:
    src = FIXTURES_ROOT / fixture_name
    snapshot = json.loads((src / "snapshot.json").read_text(encoding="utf-8"))
    run_id = str(snapshot.get("run_id") or fixture_name)
    dest = tmp_path / ".foundry" / "runs" / run_id
    shutil.copytree(src, dest)
    acceptance["workspace"] = tmp_path
    acceptance["run_id"] = run_id
    acceptance["fixture_name"] = None


@then("I write examine agent receipt draft to the run directory")
def write_examine_agent_receipt(acceptance) -> None:
    run_dir = _run_dir(acceptance)
    receipts_dir = run_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    # Steward examination receipt: no shape-steward in agent-receipt.schema.json enum yet.
    agent = {
        "schema_version": "2.2.0",
        "agent": {"name": "intake-checker", "mode": "shape"},
        "status": "completed",
        "outputs": {"summary_markdown": "Examination conversation complete."},
    }
    (receipts_dir / "agent.json").write_text(json.dumps(agent, indent=2) + "\n", encoding="utf-8")


@then(parsers.parse('the run snapshot status is "{status}"'))
def assert_snapshot_status(acceptance, status: str) -> None:
    snapshot_path = _snapshot_path(acceptance)
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot.get("status") == status


def _run_dir(acceptance) -> Path:
    workspace = Path(acceptance["workspace"])
    if acceptance.get("fixture_name"):
        return FIXTURES_ROOT / str(acceptance["fixture_name"])
    run_id = acceptance.get("run_id")
    assert run_id, "run_id not set in acceptance state"
    return workspace / ".foundry" / "runs" / str(run_id)


def _snapshot_path(acceptance) -> Path:
    if acceptance.get("fixture_name"):
        return FIXTURES_ROOT / str(acceptance["fixture_name"]) / "snapshot.json"
    return _run_dir(acceptance) / "snapshot.json"
