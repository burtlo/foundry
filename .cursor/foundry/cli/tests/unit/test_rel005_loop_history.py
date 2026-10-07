"""REL-005: repair/reverify loop history, halt reasons, retry (T7, T8)."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.engine.hooks import run_hook
from foundry_cli.engine.lifecycle import admit_visit
from foundry_cli.engine.operator import retry_run
from foundry_cli.engine.routing import evaluate_when_expression
from foundry_cli.registry import load_registry
from foundry_cli.run_service import get_run
from foundry_cli.run_store import load_snapshot, save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import FIXTURE_PORCELAIN_RECORD_GATE
from tests.unit.helpers import ledger_visit_sealed
from tests.unit.implementation_flow_helpers import workspace_with_run_fixture

BUNDLE = FOUNDRY_ROOT


def test_reverify_within_limit_expression_counts_verify_intake_seals() -> None:
    expr = "history.count('visit.sealed', node_id='verify.intake') <= config.limits.reverify"
    snapshot = {
        "config": {"limits": {"reverify": 1}},
        "ledger": [
            ledger_visit_sealed("verify.intake", visit_id="v1", seq=1),
            ledger_visit_sealed("verify.intake", visit_id="v2", seq=2),
        ],
    }
    visit = {"id": "v-ecg", "node_id": "execute.commit.gate"}
    assert evaluate_when_expression(snapshot, visit, expr) is False
    snapshot["ledger"] = snapshot["ledger"][:1]
    assert evaluate_when_expression(snapshot, visit, expr) is True


def test_commit_gate_on_examine_escalates_when_reverify_limit_exceeded(tmp_path: Path) -> None:
    """T8: second verify.intake seal blocks re-entry at execute.commit.gate."""
    workspace, run_id = workspace_with_run_fixture(tmp_path, FIXTURE_PORCELAIN_RECORD_GATE)
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    snapshot.setdefault("config", {})["limits"] = {"reverify": 1}
    snapshot["ledger"] = list(snapshot.get("ledger") or [])
    snapshot["ledger"].extend(
        [
            ledger_visit_sealed("verify.intake", visit_id="v-verify-1", seq=len(snapshot["ledger"]) + 1),
            ledger_visit_sealed("verify.intake", visit_id="v-verify-2", seq=len(snapshot["ledger"]) + 2),
        ]
    )
    visit = {
        "id": "v-ecg-t8",
        "node_id": "execute.commit.gate",
        "kind": "gate",
        "lifecycle": "examined",
    }
    result = run_hook(
        snapshot,
        visit,
        flow,
        "on_examine",
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert result["ok"] is False
    assert result.get("action") == "escalate"
    assert result.get("check_id") == "reverify-within-limit"


def test_repair_limit_exceeded_paused_with_reason_then_retry(tmp_path: Path) -> None:
    """T7: repair limit → paused + REPAIR_LIMIT_EXCEEDED → retry_run recovers."""
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

    admit_visit(
        snapshot,
        node_id="execute.repair.limit.gate",
        flow=flow,
        source="repair-route",
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )

    assert snapshot.get("status") == "paused"
    assert snapshot.get("halt_reason") == "REPAIR_LIMIT_EXCEEDED"
    reason = snapshot.get("status_reason")
    assert isinstance(reason, dict)
    assert reason.get("code") == "REPAIR_LIMIT_EXCEEDED"
    assert reason.get("retry_eligible") is True

    save_snapshot(run_dir, snapshot)
    status_payload = get_run(workspace, run_id=run_id)
    assert status_payload.get("ok") is True
    assert status_payload.get("halt_reason") == "REPAIR_LIMIT_EXCEEDED"
    assert (status_payload.get("status_reason") or {}).get("code") == "REPAIR_LIMIT_EXCEEDED"

    retry = retry_run(snapshot, reason="operator_ack")
    assert retry.get("ok") is True
    assert snapshot.get("status") == "running"
    assert snapshot.get("halt_reason") is None
    assert snapshot.get("status_reason") is None
