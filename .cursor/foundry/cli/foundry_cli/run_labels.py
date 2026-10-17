"""Stable labels derived from run snapshot fields (CLI / host / TUI)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.foundry_config import resolve_registry_bundle
from foundry_cli.registry import get_node, load_registry

_NEEDS_BY_WAIT_KIND: dict[str, str] = {
    "user_input": "Answers",
    "decision": "Approval",
    "agent": "—",
    "operator": "Action",
}

_UNKNOWN_STEP = "Unknown step"

_STATUS_LABELS: dict[str, str] = {
    "running": "Running",
    "halted": "Halted",
    "completed": "Completed",
    "paused": "Paused",
    "execution_error": "Execution error",
    "definition_error": "Definition error",
}


def run_status_label(status: str | None) -> str:
    """Human **Status** label for run list and attach header."""
    if status is None or not str(status).strip():
        return "—"
    key = str(status).strip().lower()
    mapped = _STATUS_LABELS.get(key)
    if mapped is not None:
        return mapped
    return key.replace("_", " ").title()


def needs_label(wait_kind: str | None) -> str:
    """Human **Needs** column value for a run-list or header row."""
    if wait_kind is None or not str(wait_kind).strip():
        return "—"
    kind = str(wait_kind).strip()
    mapped = _NEEDS_BY_WAIT_KIND.get(kind)
    if mapped is not None:
        return mapped
    return kind.replace("_", " ").title()


def node_step_title(node_id: str | None, flow: dict[str, Any] | None) -> str:
    """Human **Current step** label from the node package ``title``."""
    if flow is None or node_id is None or not str(node_id).strip():
        return _UNKNOWN_STEP
    try:
        node = get_node(flow, str(node_id).strip())
    except KeyError:
        return _UNKNOWN_STEP
    title = node.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return _UNKNOWN_STEP


def load_operator_flow(
    workspace: Path,
    *,
    registry: str | None = None,
) -> dict[str, Any] | None:
    """Materialized flow for operator step titles, or ``None`` when unavailable."""
    try:
        explicit = Path(registry).resolve() if registry else None
        bundle, _ = resolve_registry_bundle(workspace, explicit_registry=explicit)
        _, flow = load_registry(bundle)
        return flow
    except (FileNotFoundError, ValueError, OSError):
        return None


def phase_label(node_id: str) -> str:
    if node_id.startswith("shape."):
        return "shape"
    if node_id.startswith("execute."):
        return "execute"
    if node_id.startswith("implement."):
        return "implement"
    if node_id.startswith("verify."):
        return "verify"
    if node_id == "deliver.stub":
        return "deliver"
    return "unknown"
