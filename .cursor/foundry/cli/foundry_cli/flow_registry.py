"""Flow registry paths and node reference resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from foundry_cli.constants import DEFAULT_FLOW_ID
from foundry_cli.paths import resolve_registry_path

FLOW_REGISTRY_FILENAME = "registry.yaml"
NODE_REGISTRY_SUFFIX = "/node.yaml"


def flow_dir(bundle: Path, flow_id: str) -> Path:
    return bundle / "flows" / flow_id


def flow_registry_path(bundle: Path, flow_id: str = DEFAULT_FLOW_ID) -> Path:
    return flow_dir(bundle, flow_id) / FLOW_REGISTRY_FILENAME


def flow_registry_exists(bundle: Path, flow_id: str = DEFAULT_FLOW_ID) -> bool:
    return flow_registry_path(bundle, flow_id).is_file()


def docs_catalog_nodes_dir(repo_root: Path, flow_id: str) -> Path:
    return repo_root / "docs" / "catalog" / flow_id / "nodes"


def flow_registry_display_path(flow_id: str) -> str:
    """Stable relative path string for docs (under the registry bundle)."""
    return f"flows/{flow_id}/{FLOW_REGISTRY_FILENAME}"


def is_node_registry_ref(item: Any) -> bool:
    return (
        isinstance(item, str)
        and item.startswith("registry:nodes/")
        and item.endswith(NODE_REGISTRY_SUFFIX)
    )


def collect_node_registry_refs(raw_nodes: list[Any]) -> list[str]:
    refs: list[str] = []
    for item in raw_nodes:
        if is_node_registry_ref(item):
            refs.append(item)
    return refs


def resolve_node_registry_ref(ref: str, foundry_bundle: Path) -> dict[str, Any]:
    path = resolve_registry_path(ref, foundry_bundle)
    if not path.is_file():
        raise FileNotFoundError(f"Node registry file not found: {ref} -> {path}")
    with path.open(encoding="utf-8") as handle:
        node = yaml.safe_load(handle)
    if not isinstance(node, dict):
        raise ValueError(f"Node registry file must be a mapping: {ref}")
    node_id = node.get("id")
    if not isinstance(node_id, str) or not node_id:
        raise ValueError(f"Node registry file missing id: {ref}")
    return node


def resolve_flow_nodes(raw_nodes: list[Any], foundry_bundle: Path) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for item in raw_nodes:
        if is_node_registry_ref(item):
            resolved.append(resolve_node_registry_ref(item, foundry_bundle))
        elif isinstance(item, dict):
            resolved.append(item)
        else:
            raise ValueError(f"Invalid flow.nodes entry (expected node object or registry ref): {item!r}")
    return resolved


def load_flow_document(foundry_bundle: Path, flow_id: str = DEFAULT_FLOW_ID) -> dict[str, Any]:
    path = flow_registry_path(foundry_bundle, flow_id)
    if not path.is_file():
        raise FileNotFoundError(
            f"Flow registry not found: {flow_registry_display_path(flow_id)} "
            f"(resolved {path})"
        )
    with path.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"{path.name} must be a mapping")
    flow = document.get("flow")
    if not isinstance(flow, dict):
        raise ValueError(f"{path.name} missing flow")
    if flow.get("id") != flow_id:
        raise ValueError(f"Flow id mismatch: expected {flow_id!r}, got {flow.get('id')!r}")
    return document


def materialize_flow(flow: dict[str, Any], foundry_bundle: Path) -> dict[str, Any]:
    """Return a copy of flow with registry node refs expanded to node dicts."""
    materialized = dict(flow)
    raw_nodes = flow.get("nodes") or []
    if not isinstance(raw_nodes, list):
        raise ValueError("flow.nodes must be a list")
    materialized["nodes"] = resolve_flow_nodes(raw_nodes, foundry_bundle)
    return materialized
