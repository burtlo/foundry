"""Validate registry paths referenced by the flow (steps and node packages)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.flow_registry import collect_node_registry_refs, is_node_registry_ref
from foundry_cli.paths import resolve_registry_path
from foundry_cli.registry import load_registry


def collect_registry_instruction_refs(flow: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    nodes = flow.get("nodes") or []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        instructions = node.get("instructions")
        if isinstance(instructions, str) and instructions.startswith("registry:"):
            refs.append(instructions)
    return refs


def missing_registry_node_package_paths(raw_flow: dict[str, Any], foundry_bundle: Path) -> list[str]:
    missing: list[str] = []
    raw_nodes = raw_flow.get("nodes") or []
    for ref in collect_node_registry_refs(raw_nodes):
        try:
            path = resolve_registry_path(ref, foundry_bundle)
        except ValueError:
            missing.append(ref)
            continue
        if not path.is_file():
            missing.append(ref)
    return sorted(set(missing))


def missing_registry_instruction_paths(flow: dict[str, Any], foundry_bundle: Path) -> list[str]:
    """Return registry refs under registry:steps/ that do not resolve to an on-disk file."""
    missing: list[str] = []
    for ref in collect_registry_instruction_refs(flow):
        if not ref.startswith("registry:steps/"):
            continue
        try:
            path = resolve_registry_path(ref, foundry_bundle)
        except ValueError:
            missing.append(ref)
            continue
        if not path.is_file():
            missing.append(ref)
    return sorted(set(missing))


def missing_registry_flow_paths(
    flow: dict[str, Any],
    foundry_bundle: Path,
    *,
    raw_flow: dict[str, Any] | None = None,
) -> list[str]:
    """All unresolved registry refs required by the flow (steps and node packages)."""
    missing = missing_registry_instruction_paths(flow, foundry_bundle)
    if raw_flow is not None:
        missing.extend(missing_registry_node_package_paths(raw_flow, foundry_bundle))
    return sorted(set(missing))


def validate_registry_instruction_refs(
    flow: dict[str, Any],
    foundry_bundle: Path,
    *,
    raw_flow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return validate_registry_flow_refs(flow, foundry_bundle, raw_flow=raw_flow)


def validate_registry_flow_refs(
    flow: dict[str, Any],
    foundry_bundle: Path,
    *,
    raw_flow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    missing = missing_registry_flow_paths(flow, foundry_bundle, raw_flow=raw_flow)
    if missing:
        return {
            "ok": False,
            "code": "REFERENCE_NOT_FOUND",
            "message": "Unresolved registry references in flow",
            "missing": missing,
        }
    return {"ok": True, "missing": []}


def validate_flow_registry(foundry_bundle: Path, flow_id: str) -> dict[str, Any]:
    """Validate node package refs on the raw flow document and asset refs on materialized nodes."""
    document, flow = load_registry(foundry_bundle, flow_id=flow_id)
    raw_flow = document.get("flow")
    if not isinstance(raw_flow, dict):
        return {
            "ok": False,
            "code": "REGISTRY_ERROR",
            "message": "flow registry missing flow",
            "missing": [],
        }
    return validate_registry_flow_refs(flow, foundry_bundle, raw_flow=raw_flow)
