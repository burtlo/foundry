"""Validate registry paths referenced by the flow (steps and node packages)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from foundry_cli.engine.node_runtime_profile import RUNTIME_PROFILE_ALLOWED_KEYS
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


def _step_uses_agent_submit(node: dict[str, Any]) -> bool:
    allow = node.get("allow")
    if not isinstance(allow, dict):
        return False
    cli = allow.get("cli")
    if not isinstance(cli, list):
        return False
    return any(str(cmd) == "run.agent.submit" for cmd in cli)


def registry_node_contract_errors(flow: dict[str, Any], foundry_bundle: Path) -> list[str]:
    """Validate Step 6 node package contracts on materialized flow nodes."""
    errors: list[str] = []
    nodes = flow.get("nodes") or []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        if not node_id or str(node.get("kind") or "") != "step":
            continue

        runtime = node.get("runtime")
        if isinstance(runtime, dict):
            unknown = sorted(set(runtime.keys()) - RUNTIME_PROFILE_ALLOWED_KEYS)
            if unknown:
                errors.append(
                    f"node {node_id}: unknown runtime keys {unknown} "
                    f"(allowed: {sorted(RUNTIME_PROFILE_ALLOWED_KEYS)})"
                )
        runtime_advance = runtime.get("advance") if isinstance(runtime, dict) else None
        has_runtime_advance = isinstance(runtime_advance, str) and bool(runtime_advance.strip())

        operations = node.get("operations")
        has_operations = isinstance(operations, str) and bool(operations.strip())

        operations_file_exists = (foundry_bundle / "nodes" / node_id / "operations.yaml").is_file()

        # Runtime-bound host/task/mechanical nodes must bind both runtime.advance and operations.
        if operations_file_exists or has_runtime_advance or has_operations:
            if not has_runtime_advance:
                errors.append(
                    f"node {node_id}: missing runtime.advance for operations-bound step node"
                )
            if not has_operations:
                errors.append(
                    f"node {node_id}: missing operations for runtime-bound step node"
                )

        # Judgment nodes (agent submit) must have a task definition.
        if _step_uses_agent_submit(node):
            task_path = foundry_bundle / "tasks" / f"{node_id}.yaml"
            if not task_path.is_file():
                errors.append(
                    f"node {node_id}: missing task binding tasks/{node_id}.yaml for judgment step"
                )
    errors.extend(task_registry_contract_errors(foundry_bundle))
    return errors


def task_registry_contract_errors(foundry_bundle: Path) -> list[str]:
    """Validate judgment task YAML advance.complete_action."""
    errors: list[str] = []
    tasks_dir = foundry_bundle / "tasks"
    if not tasks_dir.is_dir():
        return errors
    for path in sorted(tasks_dir.glob("*.yaml")):
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            errors.append(f"task {path.name}: could not parse YAML")
            continue
        if not isinstance(document, dict):
            continue
        advance = document.get("advance")
        if advance is None:
            continue
        if not isinstance(advance, dict):
            errors.append(f"task {path.stem}: advance must be a mapping")
            continue
        action = advance.get("complete_action")
        if not isinstance(action, str) or not action.strip():
            errors.append(f"task {path.stem}: advance.complete_action is required when advance is set")
            continue
        action_name = action.strip()
        from foundry_cli.engine.actions import default_action_registry

        if not default_action_registry().has(action_name):
            errors.append(
                f"task {path.stem}: advance.complete_action {action_name!r} is not registered"
            )
    return errors


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
    contract_errors = registry_node_contract_errors(flow, foundry_bundle)
    if missing or contract_errors:
        return {
            "ok": False,
            "code": "REFERENCE_NOT_FOUND",
            "message": "Unresolved registry references in flow",
            "missing": missing,
            "errors": contract_errors,
        }
    return {"ok": True, "missing": [], "errors": []}


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
