"""Unit tests for declarative engine gate rules (gate.rules.yaml)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from foundry_cli.engine.expressions import evaluate_condition
from foundry_cli.engine.gate_rules import (
    examine_check_ids,
    has_gate_rules,
    load_gate_rules,
)
from foundry_cli.engine.gates import resolve_engine_gate_decision
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.helpers import seed_gate_examine_passes
from tests.unit.receipt_fixtures import (
    execute_test_agent_receipt_body,
    minimal_engine_gate_flow,
    opened_gate_visit,
    snapshot_with_execute_test_receipt,
)

EXPECTED_EXAMINE_CHECKS: dict[str, tuple[str, ...]] = {
    "execute.intake.gate": ("prior-execute-intake-sealed", "intake-receipt-sealed"),
    "execute.test.gate": ("prior-execute-test-sealed",),
    "execute.repair.limit.gate": ("repair-within-limit",),
    "execute.commit.gate": (
        "reverify-within-limit",
        "prior-execute-commit-sealed",
        "final-commit-recorded",
    ),
    "verify.intake.gate": ("prior-verify-intake-sealed", "intake-receipt-sealed"),
    "verify.acceptance.gate": ("prior-verify-acceptance-sealed",),
    "verify.code_quality.gate": ("code-quality-done-or-skipped",),
}


def _engine_gates() -> list[dict]:
    _, flow = load_registry(FOUNDRY_ROOT)
    return [
        node
        for node in flow["nodes"]
        if node.get("kind") == "gate" and node.get("decider") == "engine"
    ]


def test_every_engine_gate_has_rules_and_static_decisions_in_options() -> None:
    gates = _engine_gates()
    assert {node["id"] for node in gates} == set(EXPECTED_EXAMINE_CHECKS)
    for node in gates:
        rules = load_gate_rules(node["id"], FOUNDRY_ROOT)
        assert rules is not None, node["id"]
        assert rules["gate"] == node["id"]
        options = set(node["produces"]["options"])
        for rule in rules["rules"]:
            assert ("decision" in rule) + ("decision_from" in rule) + ("reject" in rule) == 1
            if "decision" in rule:
                assert rule["decision"] in options, (node["id"], rule["id"])


@pytest.mark.parametrize(("gate_id", "expected"), sorted(EXPECTED_EXAMINE_CHECKS.items()))
def test_examine_check_ids_come_from_node_yaml(gate_id: str, expected: tuple[str, ...]) -> None:
    assert examine_check_ids(gate_id, FOUNDRY_ROOT) == expected


@pytest.mark.parametrize(
    ("state", "expected_ok", "expected"),
    [
        ({"last_test_exit_code": 0}, True, "pass"),
        ({"last_test_exit_code": 2}, True, "repair"),
        ({"last_test_exit_code": None}, False, "EVIDENCE_MISSING"),
    ],
)
def test_execute_test_gate_state_exit_code_overrides_receipt(
    tmp_path: Path, state: dict, expected_ok: bool, expected: str
) -> None:
    snapshot, run_dir = snapshot_with_execute_test_receipt(
        tmp_path, execute_test_agent_receipt_body(exit_code=1)
    )
    snapshot["state"] = state
    visit = opened_gate_visit("v-state", "execute.test.gate")
    seed_gate_examine_passes(snapshot, visit, EXPECTED_EXAMINE_CHECKS["execute.test.gate"])
    flow = minimal_engine_gate_flow("execute.test.gate", ["pass", "repair"])
    result = resolve_engine_gate_decision(snapshot, visit, flow, run_dir=run_dir)
    assert result["ok"] is expected_ok
    assert result["decision" if expected_ok else "code"] == expected


def test_engine_gate_without_rules_file_is_unknown(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    shutil.copytree(FOUNDRY_ROOT / "nodes" / "execute.test.gate", bundle / "nodes" / "execute.test.gate")
    (bundle / "nodes" / "execute.test.gate" / "gate.rules.yaml").unlink()
    assert not has_gate_rules("execute.test.gate", bundle)
    visit = opened_gate_visit("v-unknown", "execute.test.gate")
    flow = minimal_engine_gate_flow("execute.test.gate", ["pass", "repair"])
    result = resolve_engine_gate_decision(
        {"ledger": []}, visit, flow, run_dir=tmp_path, foundry_bundle=bundle
    )
    assert result["code"] == "ENGINE_GATE_UNKNOWN"


def test_evaluate_condition_resolves_extra_names() -> None:
    names = {"evidence": {"intake": {"status": "blocked", "sealed": True}}}
    assert evaluate_condition({}, {}, "evidence.intake.status in ['blocked', 'failed']", names=names)
    assert not evaluate_condition({}, {}, "!evidence.intake.sealed", names=names)
