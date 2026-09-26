"""Unit tests for foundry_cli.catalog."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from foundry_cli.catalog import (
    build_catalog,
    build_node_index,
    collect_node_tests,
    extract_checks_used,
    normalize_connection,
)
from foundry_cli.paths import foundry_root
from foundry_cli.registry import load_registry
from tests.conftest import REPO_ROOT


@pytest.fixture
def bundle() -> Path:
    return foundry_root(REPO_ROOT)


@pytest.fixture
def flow(bundle: Path) -> dict:
    _, flow = load_registry(bundle, flow_id="implementation")
    return flow


def test_extract_checks_used_groups_lifecycle_hooks(flow: dict) -> None:
    from foundry_cli.registry import get_node

    node = get_node(flow, "shape.intake")
    checks = extract_checks_used(node)
    assert checks["on_examine"] == []
    assert checks["on_open"] == ["validate-manifest"]
    assert checks["on_close"] == []
    assert checks["on_seal"] == ["intake-receipt-sealed", "agent-receipt-sealed"]


def test_normalize_connection_preserves_on_and_loop() -> None:
    connection = {
        "id": "verify.acceptance.gate-to-shape.intake-reshape",
        "from": "verify.acceptance.gate",
        "to": "shape.intake",
        "loop": "reshape",
        "on": {"outcomes": ["completed"], "decisions": ["reshape"]},
    }
    normalized = normalize_connection(connection)
    assert normalized["id"] == connection["id"]
    assert normalized["from"] == "verify.acceptance.gate"
    assert normalized["to"] == "shape.intake"
    assert normalized["loop"] == "reshape"
    assert normalized["on"] == connection["on"]
    assert "when" not in normalized


def test_build_node_index_shape_intake(flow: dict, bundle: Path) -> None:
    index = build_node_index(
        flow,
        node_id="shape.intake",
        flow_id="implementation",
        foundry_bundle=bundle,
    )
    assert index["node_id"] == "shape.intake"
    assert index["flow_id"] == "implementation"
    assert index["kind"] == "step"
    assert index["entry"] is True
    assert index["terminal"] is False
    assert index["assets"]["instructions"] == "registry:nodes/shape.intake/instructions.md"
    assert index["assets"]["worker"]["mode"] == "shape"
    assert len(index["assets"]["receipts"]) == 2
    assert index["assets"]["artifacts"][0]["schema"] == "registry:schemas/ticket.schema.json"
    assert index["connections"]["out"][0]["to"] == "shape.examine"
    assert len(index["connections"]["in"]) == 2
    assert ".cursor/foundry/cli/tests/acceptance/features/run_context.feature" in index["tests"]
    assert index["authoring"] == "registry:nodes/shape.intake/doc.yaml"


def test_build_node_index_terminal_node(flow: dict, bundle: Path) -> None:
    index = build_node_index(
        flow,
        node_id="deliver.stub",
        flow_id="implementation",
        foundry_bundle=bundle,
    )
    assert index["terminal"] is True
    assert index["entry"] is False


def test_build_node_index_includes_authoring_when_doc_exists(
    flow: dict,
    bundle: Path,
    tmp_path: Path,
) -> None:
    doc_dir = tmp_path / "nodes" / "demo.node"
    doc_dir.mkdir(parents=True)
    (doc_dir / "doc.yaml").write_text("title: demo\n", encoding="utf-8")

    demo_node = {
        "id": "demo.node",
        "kind": "step",
        "title": "Demo",
        "instructions": "registry:nodes/demo.node/instructions.md",
    }
    demo_flow = {
        "entry": "demo.node",
        "nodes": [demo_node],
        "connections": [],
        "checks": {},
    }
    index = build_node_index(
        demo_flow,
        node_id="demo.node",
        flow_id="implementation",
        foundry_bundle=tmp_path,
    )
    assert index["authoring"] == "registry:nodes/demo.node/doc.yaml"


def test_collect_node_tests_from_tag_and_scenario_text() -> None:
    feature_dir = REPO_ROOT / ".cursor" / "foundry" / "cli" / "tests" / "acceptance" / "features"
    tests = collect_node_tests("shape.intake", feature_dir=feature_dir, repo_root=REPO_ROOT)
    assert ".cursor/foundry/cli/tests/acceptance/features/run_context.feature" in tests


def test_build_catalog_writes_index_files(bundle: Path, tmp_path: Path) -> None:
    result = build_catalog(
        foundry_bundle=bundle,
        flow_id="implementation",
        output_dir=tmp_path,
    )
    assert result["ok"] is True
    assert result["node_count"] == 29
    index_path = tmp_path / "shape.intake.index.yaml"
    assert index_path.is_file()
    index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    assert index["node_id"] == "shape.intake"


def test_build_catalog_single_node(bundle: Path, tmp_path: Path) -> None:
    result = build_catalog(
        foundry_bundle=bundle,
        flow_id="implementation",
        output_dir=tmp_path,
        node_id="shape.intake",
    )
    assert result["ok"] is True
    assert result["node_count"] == 1
    assert (tmp_path / "shape.intake.index.yaml").is_file()
    assert not (tmp_path / "shape.examine.index.yaml").exists()


def test_build_catalog_json_mode_skips_writes(bundle: Path, tmp_path: Path) -> None:
    result = build_catalog(
        foundry_bundle=bundle,
        flow_id="implementation",
        output_dir=tmp_path,
        node_id="shape.intake",
        json_mode=True,
    )
    assert result["ok"] is True
    assert result["indexes"]["shape.intake"]["node_id"] == "shape.intake"
    assert not (tmp_path / "shape.intake.index.yaml").exists()


def test_build_catalog_unknown_node(bundle: Path, tmp_path: Path) -> None:
    result = build_catalog(
        foundry_bundle=bundle,
        flow_id="implementation",
        output_dir=tmp_path,
        node_id="missing.node",
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "NODE_NOT_FOUND"
