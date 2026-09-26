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
from foundry_cli.registry import get_node
from tests.conftest import REPO_ROOT
from tests.unit.constants import (
    ACCEPTANCE_FEATURES_DIR,
    CATALOG_NODE_COUNT,
    ERROR_NODE_NOT_FOUND,
    IMPLEMENTATION_FLOW,
    NODE_DELIVER_STUB,
    NODE_SHAPE_EXAMINE,
    NODE_SHAPE_INTAKE,
    REGISTRY_INTAKE_INSTRUCTIONS,
    REGISTRY_TICKET_SCHEMA,
    RUN_CONTEXT_FEATURE,
)


def test_extract_checks_used_groups_lifecycle_hooks(flow: dict) -> None:
    node = get_node(flow, NODE_SHAPE_INTAKE)
    checks = extract_checks_used(node)
    assert checks["on_examine"] == []
    assert checks["on_open"] == ["validate-manifest"]
    assert checks["on_close"] == []
    assert checks["on_seal"] == ["intake-receipt-sealed", "agent-receipt-sealed"]


def test_normalize_connection_preserves_on_and_loop() -> None:
    connection = {
        "id": f"verify.acceptance.gate-to-{NODE_SHAPE_INTAKE}-reshape",
        "from": "verify.acceptance.gate",
        "to": NODE_SHAPE_INTAKE,
        "loop": "reshape",
        "on": {"outcomes": ["completed"], "decisions": ["reshape"]},
    }
    normalized = normalize_connection(connection)
    assert normalized["id"] == connection["id"]
    assert normalized["from"] == "verify.acceptance.gate"
    assert normalized["to"] == NODE_SHAPE_INTAKE
    assert normalized["loop"] == "reshape"
    assert normalized["on"] == connection["on"]
    assert "when" not in normalized


def test_build_node_index_shape_intake(flow: dict, bundle: Path) -> None:
    index = build_node_index(
        flow,
        node_id=NODE_SHAPE_INTAKE,
        flow_id=IMPLEMENTATION_FLOW,
        foundry_bundle=bundle,
    )
    assert index["node_id"] == NODE_SHAPE_INTAKE
    assert index["flow_id"] == IMPLEMENTATION_FLOW
    assert index["kind"] == "step"
    assert index["entry"] is True
    assert index["terminal"] is False
    assert index["assets"]["instructions"] == REGISTRY_INTAKE_INSTRUCTIONS
    assert index["assets"]["worker"]["mode"] == "shape"
    assert len(index["assets"]["receipts"]) == 2
    assert index["assets"]["artifacts"][0]["schema"] == REGISTRY_TICKET_SCHEMA
    assert index["connections"]["out"][0]["to"] == NODE_SHAPE_EXAMINE
    assert len(index["connections"]["in"]) == 2
    assert RUN_CONTEXT_FEATURE in index["tests"]
    assert index["authoring"] == "registry:nodes/shape.intake/doc.yaml"


def test_build_node_index_terminal_node(flow: dict, bundle: Path) -> None:
    index = build_node_index(
        flow,
        node_id=NODE_DELIVER_STUB,
        flow_id=IMPLEMENTATION_FLOW,
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
        flow_id=IMPLEMENTATION_FLOW,
        foundry_bundle=tmp_path,
    )
    assert index["authoring"] == "registry:nodes/demo.node/doc.yaml"


def test_collect_node_tests_from_tag_and_scenario_text() -> None:
    tests = collect_node_tests(NODE_SHAPE_INTAKE, feature_dir=ACCEPTANCE_FEATURES_DIR, repo_root=REPO_ROOT)
    assert RUN_CONTEXT_FEATURE in tests


def test_build_catalog_writes_index_files(bundle: Path, tmp_path: Path) -> None:
    result = build_catalog(
        foundry_bundle=bundle,
        flow_id=IMPLEMENTATION_FLOW,
        output_dir=tmp_path,
    )
    assert result["ok"] is True
    assert result["node_count"] == CATALOG_NODE_COUNT
    index_path = tmp_path / f"{NODE_SHAPE_INTAKE}.index.yaml"
    assert index_path.is_file()
    index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    assert index["node_id"] == NODE_SHAPE_INTAKE


def test_build_catalog_single_node(bundle: Path, tmp_path: Path) -> None:
    result = build_catalog(
        foundry_bundle=bundle,
        flow_id=IMPLEMENTATION_FLOW,
        output_dir=tmp_path,
        node_id=NODE_SHAPE_INTAKE,
    )
    assert result["ok"] is True
    assert result["node_count"] == 1
    assert (tmp_path / f"{NODE_SHAPE_INTAKE}.index.yaml").is_file()
    assert not (tmp_path / "shape.examine.index.yaml").exists()


def test_build_catalog_json_mode_skips_writes(bundle: Path, tmp_path: Path) -> None:
    result = build_catalog(
        foundry_bundle=bundle,
        flow_id=IMPLEMENTATION_FLOW,
        output_dir=tmp_path,
        node_id=NODE_SHAPE_INTAKE,
        json_mode=True,
    )
    assert result["ok"] is True
    assert result["indexes"][NODE_SHAPE_INTAKE]["node_id"] == NODE_SHAPE_INTAKE
    assert not (tmp_path / f"{NODE_SHAPE_INTAKE}.index.yaml").exists()


def test_build_catalog_unknown_node(bundle: Path, tmp_path: Path) -> None:
    result = build_catalog(
        foundry_bundle=bundle,
        flow_id=IMPLEMENTATION_FLOW,
        output_dir=tmp_path,
        node_id="missing.node",
    )
    assert result["ok"] is False
    assert result["error"]["code"] == ERROR_NODE_NOT_FOUND
