"""REL-004: admit_visit honors on_examine skip / escalate (kernel honesty)."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.engine.lifecycle import admit_visit
from foundry_cli.engine.verify_step_executor import VERIFY_CODE_QUALITY_NODE, VERIFY_CODE_REVIEW_NODE
from foundry_cli.registry import load_registry
from foundry_cli.run_store import load_snapshot, save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import FIXTURE_PORCELAIN_RECORD_GATE, IMPLEMENTATION_FLOW, TEST_RUN_UUID
from tests.unit.helpers import ledger_visit_sealed
from tests.unit.implementation_flow_helpers import workspace_with_run_fixture
from tests.unit.shape_flow_helpers import shape_test_workspace

BUNDLE = FOUNDRY_ROOT


def _verify_prereq_ledger() -> list[dict]:
    return [
        ledger_visit_sealed("verify.acceptance", visit_id="v-acc", seq=1),
        {
            "seq": 2,
            "type": "gate.resolved",
            "node_id": "verify.acceptance.gate",
            "visit_id": "v-acc-g",
            "payload": {"decision": "pass"},
        },
    ]


def _verify_snapshot(tmp_path: Path, *, review_enabled: bool) -> tuple[Path, dict, dict, Path]:
    workspace = shape_test_workspace(tmp_path)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / "lifecycle-admit-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot: dict = {
        "schema_version": "1.0.0",
        "run_id": "lifecycle-admit-001",
        "run_uuid": TEST_RUN_UUID,
        "flow_id": IMPLEMENTATION_FLOW,
        "status": "running",
        "workspace": str(workspace),
        "config": {
            "workspace": str(workspace),
            "review": {"enabled": review_enabled},
        },
        "state": {
            "approved_ac": "AC",
            "feature_branch": "foundry/test",
            "default_branch": "main",
        },
        "visits": [],
        "ledger": _verify_prereq_ledger(),
    }
    save_snapshot(run_dir, snapshot)
    return workspace, snapshot, flow, run_dir


def test_admit_visit_skips_verify_code_quality_when_review_disabled(tmp_path: Path) -> None:
    workspace, snapshot, flow, run_dir = _verify_snapshot(tmp_path, review_enabled=False)

    visit = admit_visit(
        snapshot,
        node_id=VERIFY_CODE_QUALITY_NODE,
        flow=flow,
        source="test",
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )

    assert visit.get("node_id") == VERIFY_CODE_REVIEW_NODE
    assert visit.get("lifecycle") == "opened"

    sealed = [e for e in snapshot.get("ledger", []) if e.get("type") == "visit.sealed"]
    cq_sealed = [e for e in sealed if e.get("node_id") == VERIFY_CODE_QUALITY_NODE]
    assert len(cq_sealed) == 1
    assert (cq_sealed[0].get("payload") or {}).get("outcome") == "not_applicable"

    assert not any(e.get("node_id") == "verify.code_quality.gate" for e in sealed)
    taken = [
        e
        for e in snapshot.get("ledger", [])
        if e.get("type") == "connection.taken"
        and (e.get("payload") or {}).get("connection_id") == "verify.code_quality-to-verify.code_review-skipped"
    ]
    assert len(taken) == 1


def test_admit_visit_escalates_repair_limit_gate_when_over_limit(tmp_path: Path) -> None:
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
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

    visit = admit_visit(
        snapshot,
        node_id="execute.repair.limit.gate",
        flow=flow,
        source="repair-route",
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )

    assert snapshot.get("status") == "paused"
    assert visit.get("node_id") == "execute.repair.limit.gate"
    assert visit.get("lifecycle") == "examined"
    status_events = [
        e
        for e in snapshot.get("ledger", [])
        if e.get("type") == "run.status_changed" and (e.get("payload") or {}).get("new_status") == "paused"
    ]
    assert status_events
