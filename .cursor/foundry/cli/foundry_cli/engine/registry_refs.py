"""Validate registry paths referenced by the flow (steps, worker prompts, contracts)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.paths import resolve_registry_path


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


def collect_registry_worker_refs(flow: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (prompt_ref, contract_ref) for each step node with a worker binding."""
    pairs: list[tuple[str, str]] = []
    nodes = flow.get("nodes") or []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        worker = node.get("worker")
        if not isinstance(worker, dict):
            continue
        prompt = worker.get("prompt")
        contract = worker.get("contract")
        if isinstance(prompt, str) and isinstance(contract, str):
            pairs.append((prompt, contract))
    return pairs


def missing_registry_worker_paths(flow: dict[str, Any], foundry_bundle: Path) -> list[str]:
    """Return registry worker prompt/contract refs that do not resolve to on-disk files."""
    missing: list[str] = []
    for prompt_ref, contract_ref in collect_registry_worker_refs(flow):
        for ref in (prompt_ref, contract_ref):
            if not isinstance(ref, str) or not ref.startswith("registry:"):
                missing.append(str(ref))
                continue
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


def missing_registry_flow_paths(flow: dict[str, Any], foundry_bundle: Path) -> list[str]:
    """All unresolved registry refs required by the flow (steps + worker assets)."""
    missing = missing_registry_instruction_paths(flow, foundry_bundle)
    missing.extend(missing_registry_worker_paths(flow, foundry_bundle))
    return sorted(set(missing))


def validate_registry_instruction_refs(flow: dict[str, Any], foundry_bundle: Path) -> dict[str, Any]:
    return validate_registry_flow_refs(flow, foundry_bundle)


def validate_registry_flow_refs(flow: dict[str, Any], foundry_bundle: Path) -> dict[str, Any]:
    missing = missing_registry_flow_paths(flow, foundry_bundle)
    if missing:
        return {
            "ok": False,
            "code": "REFERENCE_NOT_FOUND",
            "message": "Unresolved registry references in flow",
            "missing": missing,
        }
    return {"ok": True, "missing": []}
