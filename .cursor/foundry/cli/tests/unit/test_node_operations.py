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
    assert "transition_complete" in mechanism_ids


def test_load_shape_examine_operations() -> None:
    bundle = FOUNDRY_ROOT
    data = load_operations("registry:nodes/shape.examine/operations.yaml", bundle)

    assert data["node_id"] == "shape.examine"
    assert data["policy"]["admission"][0]["check"] == "prior-shape-intake-sealed"
    mechanism_ids = [step["id"] for step in data["mechanism"]]
    assert "patch_examination_state" in mechanism_ids
    assert "transition_complete" in mechanism_ids
    connections = data["policy"]["routing"]["connections"]
    assert {c["to"] for c in connections} == {"shape.present", "shape.examine.gate"}
