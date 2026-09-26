"""Unit tests for foundry_cli.docgen."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from foundry_cli.docgen import build_flow_doc, build_node_doc, rel_link, write_generated_docs
from foundry_cli.paths import foundry_root
from foundry_cli.registry import load_registry

CLI_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = CLI_DIR.parents[2]
FOUNDRY_ROOT = foundry_root(REPO_ROOT)


@pytest.fixture
def flow_bundle() -> tuple[dict, Path]:
    _, flow = load_registry(FOUNDRY_ROOT, flow_id="implementation")
    return flow, FOUNDRY_ROOT


def _target_exists(from_file: Path, href: str) -> bool:
    return (from_file.parent / href).resolve().exists()


def test_shape_intake_doc_contains_required_sections(flow_bundle) -> None:
    flow, bundle = flow_bundle
    doc = build_node_doc("shape.intake", flow, bundle, REPO_ROOT)
    for heading in (
        "## Lifecycle",
        "## Sequence",
        "## Ledger excerpt",
        "## References",
        "## Permissions",
        "### Engine-only surfaces",
        "## Artifacts",
        "#### Ticket fields",
        "#### Downstream consumption",
        "## Receipts",
        "## Worker",
        "#### Worker concern ownership",
        "## Connections",
        "## Check catalog",
        "## Gaps",
        "## Concepts",
        "## Node summary",
    ):
        assert heading in doc


def test_shape_intake_doc_contains_required_links(flow_bundle) -> None:
    flow, bundle = flow_bundle
    output_dir = REPO_ROOT / "docs" / "nodes"
    doc = build_node_doc(
        "shape.intake",
        flow,
        bundle,
        REPO_ROOT,
        output_nodes_dir=output_dir,
    )
    from_file = output_dir / "shape.intake.md"

    required_hrefs = [
        "../../.cursor/foundry/nodes/shape.intake/instructions.md",
        "../../.cursor/agents/intake-checker.shape.md",
        "../../.cursor/foundry/workers/intake-checker.shape/contract.yaml",
        "../../.cursor/foundry/schemas/intake-receipt.schema.json",
        "../../.cursor/foundry/schemas/agent-receipt.schema.json",
        "../../.cursor/foundry/schemas/ticket.schema.json",
        "../../.cursor/foundry/schemas/app-manifest.schema.json",
        "../../.cursor/foundry/catalog/nodes/shape.intake.index.yaml",
    ]
    generated_node_hrefs = ["shape.examine.md"]
    for href in required_hrefs:
        assert f"]({href})" in doc
        assert _target_exists(from_file, href), f"missing target for {href}"
    for href in generated_node_hrefs:
        assert f"]({href})" in doc

    for check_id in ("validate-manifest", "intake-receipt-sealed", "agent-receipt-sealed"):
        assert f"`{check_id}`" in doc

    assert "`schema_version`" in doc
    assert "`normalized_translation`" in doc
    assert "reads `shape.intake.ticket`" in doc
    assert "## Ledger excerpt" in doc
    assert "| 7 | `artifact.linked` |" in doc


def test_shape_intake_doc_has_lifecycle_mermaid(flow_bundle) -> None:
    flow, bundle = flow_bundle
    doc = build_node_doc("shape.intake", flow, bundle, REPO_ROOT)
    assert "```mermaid" in doc
    assert "stateDiagram-v2" in doc
    assert "validate-manifest" in doc
    assert "intake-receipt-sealed" in doc


def test_write_generated_docs_shape_intake(tmp_path) -> None:
    _, flow = load_registry(FOUNDRY_ROOT, flow_id="implementation")
    output_dir = tmp_path / "generated"
    written = write_generated_docs(
        flow=flow,
        foundry_bundle=FOUNDRY_ROOT,
        repo_root=REPO_ROOT,
        node_ids=["shape.intake"],
        output_dir=output_dir,
        write_index=False,
    )
    paths = {path.name for path in written}
    assert "shape.intake.md" in paths
    worker_paths = {p.as_posix().split("catalog/")[-1] for p in written if "workers" in p.as_posix()}
    assert "workers/intake-checker.shape.md" in worker_paths


def test_build_flow_doc_contains_graph_and_connections(flow_bundle) -> None:
    flow, bundle = flow_bundle
    doc = build_flow_doc(flow, bundle, REPO_ROOT, output_dir=REPO_ROOT / "docs")
    assert "# Flow: `implementation`" in doc
    assert "```mermaid" in doc
    assert "flowchart TD" in doc
    assert "## Concepts" in doc
    assert "## Connections" in doc
    assert "shape.intake-to-shape.examine" in doc
    assert "## Check catalog" in doc
    assert "`validate-manifest`" in doc
    assert "concepts/graph.md" in doc


def test_rel_link_uses_posix_paths(tmp_path) -> None:
    from_file = tmp_path / "docs" / "nodes" / "shape.intake.md"
    target = tmp_path / ".cursor" / "foundry" / "nodes" / "shape.intake" / "instructions.md"
    link = rel_link(from_file, target, "instructions")
    assert link.startswith("[instructions](")
    assert "\\" not in link
