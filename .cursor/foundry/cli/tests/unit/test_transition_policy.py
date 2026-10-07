"""Unit tests for transition-time engine policy."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.constants import EVENT_RECEIPT_LINKED
from foundry_cli.engine.transition_policy import enforce_transition_policy
from foundry_cli.registry import load_registry
from tests.unit.helpers import make_visit

BUNDLE = Path(__file__).resolve().parents[3]


def _link_intake_receipt(snapshot: dict, visit_id: str, *, status: str) -> None:
    ledger = snapshot.setdefault("ledger", [])
    ledger.append(
        {
            "type": EVENT_RECEIPT_LINKED,
            "visit_id": visit_id,
            "payload": {"schema": "registry:schemas/intake-receipt.schema.json"},
        }
    )
    run_dir = snapshot["_run_dir"]
    receipts = run_dir / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    (receipts / "intake.json").write_text(
        json.dumps({"status": status, "step_id": "shape.intake"}),
        encoding="utf-8",
    )


def _flow() -> dict:
    _, flow = load_registry(BUNDLE)
    return flow


def test_shape_intake_blocks_transition_when_receipt_blocked(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot: dict = {"_run_dir": run_dir}
    visit = make_visit("v-001")
    visit["node_id"] = "shape.intake"
    _link_intake_receipt(snapshot, "v-001", status="blocked")

    result = enforce_transition_policy(
        snapshot,
        visit,
        flow=_flow(),
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )

    assert result["ok"] is False
    assert result["code"] == "INTAKE_BLOCKED"


def test_shape_intake_allows_transition_when_receipt_passed(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot: dict = {"_run_dir": run_dir}
    visit = make_visit("v-001")
    visit["node_id"] = "shape.intake"
    _link_intake_receipt(snapshot, "v-001", status="passed")

    result = enforce_transition_policy(
        snapshot,
        visit,
        flow=_flow(),
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )

    assert result["ok"] is True


def test_other_nodes_skip_intake_policy(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot: dict = {}
    visit = make_visit("v-002")
    visit["node_id"] = "shape.examine"

    result = enforce_transition_policy(
        snapshot,
        visit,
        flow=_flow(),
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )

    assert result["ok"] is True


def test_execute_verify_intake_transitions_block_when_receipt_blocked(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    flow = _flow()
    for node_id in ("execute.intake", "verify.intake"):
        snapshot: dict = {"_run_dir": run_dir}
        visit = make_visit(f"v-{node_id}")
        visit["node_id"] = node_id
        _link_intake_receipt(snapshot, str(visit["id"]), status="blocked")

        result = enforce_transition_policy(
            snapshot,
            visit,
            flow=flow,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
        )

        assert result["ok"] is False
        assert result["code"] == "INTAKE_BLOCKED"
