"""Load flow registry documents and resolve node packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.constants import DEFAULT_FLOW_ID
from foundry_cli.flow_registry import load_flow_document, materialize_flow


def load_registry(
    foundry_bundle: Path,
    flow_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved_flow_id = flow_id or DEFAULT_FLOW_ID
    document = load_flow_document(foundry_bundle, resolved_flow_id)
    flow = document.get("flow")
    if not isinstance(flow, dict):
        raise ValueError("flow registry missing flow")
    materialized = materialize_flow(flow, foundry_bundle)
    return document, materialized


def get_node(flow: dict[str, Any], node_id: str) -> dict[str, Any]:
    nodes = flow.get("nodes") or []
    for node in nodes:
        if isinstance(node, dict) and node.get("id") == node_id:
            return node
    raise KeyError(node_id)


def normalize_receipts(node: dict[str, Any]) -> list[str]:
    receipts = node.get("receipts")
    if receipts is None:
        return []
    if isinstance(receipts, str):
        return [receipts]
    if isinstance(receipts, list):
        return [str(item) for item in receipts]
    raise ValueError("node receipts must be a string or list")
