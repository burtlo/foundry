"""Unit tests for foundry_cli.docgen."""

from __future__ import annotations

from foundry_cli.docgen import build_flow_doc, build_node_doc, rel_link, write_generated_docs
from foundry_cli.registry import load_registry
from tests.conftest import REPO_ROOT
from tests.unit.constants import (
    DOCS_DIR,
    DOCS_NODES_DIR,
    IMPLEMENTATION_FLOW,
    NODE_SHAPE_EXAMINE,
    NODE_SHAPE_INTAKE,
)
from tests.unit.helpers import target_exists


def test_shape_intake_doc_contains_required_sections(flow_bundle) -> None:
    flow, bundle = flow_bundle
    doc = build_node_doc(NODE_SHAPE_INTAKE, flow, bundle, REPO_ROOT)
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
        "## Connections",
        "## Check catalog",
        "## Gaps",
        "## Concepts",
        "## Node summary",
    ):
        assert heading in doc
    assert "_No worker bound._" in doc


def test_shape_intake_doc_contains_required_links(flow_bundle) -> None:
    flow, bundle = flow_bundle
    doc = build_node_doc(
        NODE_SHAPE_INTAKE,
        flow,
        bundle,
        REPO_ROOT,
        output_nodes_dir=DOCS_NODES_DIR,
    )
    from_file = DOCS_NODES_DIR / f"{NODE_SHAPE_INTAKE}.md"

    required_hrefs = [
        "../../.cursor/foundry/schemas/intake-receipt.schema.json",
        "../../.cursor/foundry/schemas/agent-receipt.schema.json",
        "../../.cursor/foundry/schemas/ticket.schema.json",
        "../../.cursor/foundry/schemas/app-manifest.schema.json",
        f"../catalog/implementation/nodes/{NODE_SHAPE_INTAKE}.index.yaml",
    ]
    generated_node_hrefs = [f"{NODE_SHAPE_EXAMINE}.md"]
    for href in required_hrefs:
        assert f"]({href})" in doc
        assert target_exists(from_file, href), f"missing target for {href}"
    for href in generated_node_hrefs:
        assert f"]({href})" in doc

    for check_id in ("validate-manifest", "intake-receipt-sealed", "agent-receipt-sealed"):
        assert f"`{check_id}`" in doc

    assert "`schema_version`" in doc
    assert "`normalized_translation`" in doc
    assert f"reads `{NODE_SHAPE_INTAKE}.ticket`" in doc
    assert "## Ledger excerpt" in doc
    assert "| 7 | `artifact.linked` |" in doc


def test_shape_intake_doc_has_lifecycle_mermaid(flow_bundle) -> None:
    flow, bundle = flow_bundle
    doc = build_node_doc(NODE_SHAPE_INTAKE, flow, bundle, REPO_ROOT)
    assert "```mermaid" in doc
    assert "stateDiagram-v2" in doc
    assert "validate-manifest" in doc
    assert "intake-receipt-sealed" in doc


def test_write_generated_docs_shape_intake(bundle, tmp_path) -> None:
    _, flow = load_registry(bundle, flow_id=IMPLEMENTATION_FLOW)
    output_dir = tmp_path / "generated"
    written = write_generated_docs(
        flow=flow,
        foundry_bundle=bundle,
        repo_root=REPO_ROOT,
        node_ids=[NODE_SHAPE_INTAKE],
        output_dir=output_dir,
        write_index=False,
    )
    paths = {path.name for path in written}
    assert f"{NODE_SHAPE_INTAKE}.md" in paths


def test_build_flow_doc_contains_graph_and_connections(flow_bundle) -> None:
    flow, bundle = flow_bundle
    doc = build_flow_doc(flow, bundle, REPO_ROOT, output_dir=DOCS_DIR)
    assert f"# Flow: `{IMPLEMENTATION_FLOW}`" in doc
    assert "```mermaid" in doc
    assert "flowchart TD" in doc
    assert "## Concepts" in doc
    assert "## Connections" in doc
    assert f"{NODE_SHAPE_INTAKE}-to-{NODE_SHAPE_EXAMINE}" in doc
    assert "## Check catalog" in doc
    assert "`validate-manifest`" in doc
    assert "concepts/graph.md" in doc


def test_rel_link_uses_posix_paths(tmp_path) -> None:
    from_file = tmp_path / "docs" / "nodes" / f"{NODE_SHAPE_INTAKE}.md"
    target = tmp_path / ".cursor" / "foundry" / "nodes" / NODE_SHAPE_INTAKE / "judgment.md"
    link = rel_link(from_file, target, "judgment")
    assert link.startswith("[judgment](")
    assert "\\" not in link
