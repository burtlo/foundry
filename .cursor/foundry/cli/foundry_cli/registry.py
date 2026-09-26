"""Load factory-flow.yaml registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_registry(foundry_bundle: Path, flow_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    flow_path = foundry_bundle / "flows" / "factory-flow.yaml"
    with flow_path.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if not isinstance(document, dict):
        raise ValueError("factory-flow.yaml must be a mapping")
    flow = document.get("flow")
    if not isinstance(flow, dict):
        raise ValueError("factory-flow.yaml missing flow")
    if flow_id and flow.get("id") != flow_id:
        raise ValueError(f"Flow id mismatch: expected {flow_id!r}, got {flow.get('id')!r}")
    return document, flow


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
