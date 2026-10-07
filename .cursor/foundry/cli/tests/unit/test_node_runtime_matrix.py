"""Unit tests for implementation-flow node runtime matrix generator."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.engine.node_runtime_matrix import (
    build_node_runtime_matrix,
    implementation_flow_node_ids,
    render_node_runtime_matrix_markdown,
    write_node_runtime_matrix,
)
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import CATALOG_NODE_COUNT, IMPLEMENTATION_FLOW, NODE_SHAPE_INTAKE

REPO_ROOT = FOUNDRY_ROOT.parent.parent
EXPECTED_MATRIX = REPO_ROOT / "docs" / "generated" / "engine-node-runtime-matrix.md"


def test_implementation_flow_lists_all_registry_nodes() -> None:
    ids = implementation_flow_node_ids(FOUNDRY_ROOT, IMPLEMENTATION_FLOW)
    assert len(ids) == CATALOG_NODE_COUNT
    assert ids[0] == NODE_SHAPE_INTAKE
    assert "deliver.stub" in ids


def test_matrix_row_shape_intake_fields() -> None:
    rows = build_node_runtime_matrix(FOUNDRY_ROOT, IMPLEMENTATION_FLOW)
    by_id = {row.node_id: row for row in rows}
    intake = by_id[NODE_SHAPE_INTAKE]
    assert intake.kind == "step"
    assert intake.python_complete_fn == "run_shape_intake_complete"
    assert intake.operations_yaml is True
    assert intake.operations_bound is True
    assert "host_advance" in intake.advance_classifier
    assert intake.boundary_status == "implemented"


def test_render_markdown_includes_table_header() -> None:
    rows = build_node_runtime_matrix(FOUNDRY_ROOT, IMPLEMENTATION_FLOW)
    md = render_node_runtime_matrix_markdown(rows, flow_id=IMPLEMENTATION_FLOW)
    assert "| node_id | kind |" in md
    assert NODE_SHAPE_INTAKE in md


def test_write_matrix_matches_committed_artifact(tmp_path: Path) -> None:
    out = tmp_path / "matrix.md"
    result = write_node_runtime_matrix(FOUNDRY_ROOT, output_path=out)
    assert result["ok"] is True
    assert result["node_count"] == CATALOG_NODE_COUNT
    assert any("python-only node without bound operations" in item for item in result["warnings"])
    assert out.is_file()
    if EXPECTED_MATRIX.is_file():
        assert out.read_text(encoding="utf-8") == EXPECTED_MATRIX.read_text(encoding="utf-8")
