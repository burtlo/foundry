"""Unit tests for node operations manifests."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.node_operations import load_operations

FOUNDRY_ROOT = Path(__file__).resolve().parents[3]


def test_load_shape_intake_operations() -> None:
    bundle = FOUNDRY_ROOT
    data = load_operations("registry:nodes/shape.intake/operations.yaml", bundle)

    assert data["node_id"] == "shape.intake"
    assert data["policy"]["admission"][0]["check"] == "validate-manifest"
    mechanism_ids = [step["id"] for step in data["mechanism"]]
    assert "deterministic_intake_complete" in mechanism_ids
    assert mechanism_ids == ["deterministic_intake_complete"]


def test_load_execute_intake_operations() -> None:
    bundle = FOUNDRY_ROOT
    data = load_operations("registry:nodes/execute.intake/operations.yaml", bundle)

    assert data["node_id"] == "execute.intake"
    mechanism = data["mechanism"]
    assert len(mechanism) == 1
    assert mechanism[0]["id"] == "deterministic_intake_complete"
    assert mechanism[0]["action"] == "visit.intake.complete"


def test_load_verify_intake_operations() -> None:
    bundle = FOUNDRY_ROOT
    data = load_operations("registry:nodes/verify.intake/operations.yaml", bundle)

    assert data["node_id"] == "verify.intake"
    mechanism = data["mechanism"]
    assert len(mechanism) == 1
    assert mechanism[0]["id"] == "deterministic_intake_complete"
    assert mechanism[0]["action"] == "visit.intake.complete"


def test_load_deliver_stub_operations() -> None:
    bundle = FOUNDRY_ROOT
    data = load_operations("registry:nodes/deliver.stub/operations.yaml", bundle)

    assert data["node_id"] == "deliver.stub"
    mechanism = data["mechanism"]
    assert len(mechanism) == 1
    assert mechanism[0]["id"] == "deterministic_deliver_stub_complete"
    assert mechanism[0]["action"] == "visit.deliver.stub.complete"


def test_load_shape_examine_operations() -> None:
    bundle = FOUNDRY_ROOT
    data = load_operations("registry:nodes/shape.examine/operations.yaml", bundle)

    assert data["node_id"] == "shape.examine"
    assert "note" in data
    assert data["policy"]["admission"][0]["check"] == "prior-shape-intake-sealed"
    connections = data["policy"]["routing"]["connections"]
    assert {c["to"] for c in connections} == {"shape.present", "shape.examine.gate"}
