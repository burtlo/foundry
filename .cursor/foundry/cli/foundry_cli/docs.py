"""Shared documentation build pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.catalog import build_catalog
from foundry_cli.docgen import write_generated_docs
from foundry_cli.errors import error, ok
from foundry_cli.parser import build_parser
from foundry_cli.paths import repo_root_from_bundle, resolve_generated_docs_dir
from foundry_cli.registry import get_node, load_registry


def build_docs(
    *,
    workspace: Path,
    bundle: Path,
    flow_id: str = "implementation",
    node_id: str | None = None,
    output_dir: Path | None = None,
    smoke: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Build catalog indexes and generate node documentation."""
    repo = repo_root if repo_root is not None else repo_root_from_bundle(bundle)
    try:
        _, flow = load_registry(bundle, flow_id=flow_id)
    except ValueError as exc:
        return error("INVALID_FLOW", str(exc))

    all_flow_nodes = [
        str(node["id"])
        for node in (flow.get("nodes") or [])
        if isinstance(node, dict) and node.get("id")
    ]

    if smoke:
        node_ids = ["shape.intake"]
        catalog_node_id = "shape.intake"
        write_index = False
    elif node_id:
        node_ids = [node_id]
        catalog_node_id = node_id
        write_index = False
        try:
            get_node(flow, node_id)
        except KeyError:
            return error("NODE_NOT_FOUND", f"Node not found in flow registry: {node_id!r}")
    else:
        node_ids = all_flow_nodes
        catalog_node_id = None
        write_index = True

    catalog_result = build_catalog(
        foundry_bundle=bundle,
        flow_id=flow_id,
        node_id=catalog_node_id,
        json_mode=False,
    )
    if not catalog_result.get("ok"):
        return catalog_result

    try:
        out = resolve_generated_docs_dir(repo, output_dir)
    except ValueError as exc:
        return error("INVALID_DOCS_OUTPUT", str(exc))
    written = write_generated_docs(
        flow=flow,
        foundry_bundle=bundle,
        repo_root=repo,
        node_ids=node_ids,
        output_dir=out,
        write_index=write_index,
        cli_parser=build_parser(),
    )
    return ok(
        flow_id=flow_id,
        output_dir=str(out.resolve()),
        generated_count=len(written),
        generated=[str(path) for path in written],
    )
