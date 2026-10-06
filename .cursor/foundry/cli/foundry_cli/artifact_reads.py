"""Resolve flow `reads.artifacts` declarations for steward context."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from foundry_cli.ledger import ledger_events
from foundry_cli.paths import resolve_run_uri


def parse_qualified_artifact_ref(ref: str) -> tuple[str, str]:
    """Split ``node-id.artifact-id`` (e.g. ``shape.present.presentation``)."""
    if "." not in ref:
        raise ValueError(f"Invalid qualified artifact ref: {ref!r}")
    producer_node_id, artifact_id = ref.rsplit(".", 1)
    if not producer_node_id or not artifact_id:
        raise ValueError(f"Invalid qualified artifact ref: {ref!r}")
    return producer_node_id, artifact_id


def _find_visit(snapshot: dict[str, Any], visit_id: str) -> dict[str, Any] | None:
    active = snapshot.get("active_visit")
    if isinstance(active, dict) and str(active.get("id")) == visit_id:
        return active
    visits = snapshot.get("visits")
    if isinstance(visits, list):
        for visit in visits:
            if isinstance(visit, dict) and str(visit.get("id")) == visit_id:
                return visit
    return None


def _visit_admission_source(snapshot: dict[str, Any], visit_id: str) -> str | None:
    for event in ledger_events(snapshot):
        if not isinstance(event, dict) or event.get("type") != "visit.admitted":
            continue
        if str(event.get("visit_id")) != visit_id:
            continue
        payload = event.get("payload") or {}
        source = payload.get("source")
        if isinstance(source, str) and source.strip():
            return source.strip()
        return None
    return None


def _visit_parent_id(snapshot: dict[str, Any], visit_id: str) -> str | None:
    source = _visit_admission_source(snapshot, visit_id)
    if not source:
        return None
    for event in reversed(ledger_events(snapshot)):
        if not isinstance(event, dict) or event.get("type") != "connection.taken":
            continue
        payload = event.get("payload") or {}
        if str(payload.get("connection_id")) != source:
            continue
        parent_id = event.get("visit_id")
        return str(parent_id) if parent_id else None
    return None


def ancestor_visit_ids_nearest_first(snapshot: dict[str, Any], visit_id: str) -> list[str]:
    """Routed ancestors of ``visit_id``, nearest parent first."""
    ancestors: list[str] = []
    seen: set[str] = set()
    current = visit_id
    while True:
        parent = _visit_parent_id(snapshot, current)
        if not parent or parent in seen:
            break
        seen.add(parent)
        ancestors.append(parent)
        current = parent
    return ancestors


def artifact_linked_uri(snapshot: dict[str, Any], *, visit_id: str, artifact_id: str) -> str | None:
    for event in reversed(ledger_events(snapshot)):
        if not isinstance(event, dict) or event.get("type") != "artifact.linked":
            continue
        if str(event.get("visit_id")) != visit_id:
            continue
        payload = event.get("payload") or {}
        if payload.get("artifact_id") != artifact_id:
            continue
        uri = payload.get("uri")
        return str(uri) if isinstance(uri, str) and uri.strip() else None
    return None


def nearest_sealed_producer_visit_id(
    snapshot: dict[str, Any],
    *,
    from_visit_id: str,
    producer_node_id: str,
) -> str | None:
    for ancestor_id in ancestor_visit_ids_nearest_first(snapshot, from_visit_id):
        visit = _find_visit(snapshot, ancestor_id)
        if visit is None:
            continue
        if str(visit.get("node_id")) != producer_node_id:
            continue
        if str(visit.get("lifecycle")) != "sealed":
            continue
        if str(visit.get("outcome")) != "completed":
            continue
        return ancestor_id
    return None


def resolve_nearest_sealed_ancestor_artifact(
    snapshot: dict[str, Any],
    *,
    qualified_ref: str,
    from_visit_id: str,
    run_dir: Path,
) -> dict[str, str] | None:
    producer_node_id, artifact_id = parse_qualified_artifact_ref(qualified_ref)
    producer_visit_id = nearest_sealed_producer_visit_id(
        snapshot,
        from_visit_id=from_visit_id,
        producer_node_id=producer_node_id,
    )
    if not producer_visit_id:
        return None
    uri = artifact_linked_uri(snapshot, visit_id=producer_visit_id, artifact_id=artifact_id)
    if not uri:
        return None
    resolved_path = str(resolve_run_uri(uri, run_dir, producer_visit_id))
    return {"resolved_uri": uri, "resolved_path": resolved_path}


def resolve_reads_artifacts(
    artifacts: list[dict[str, Any]],
    *,
    snapshot: dict[str, Any],
    visit_id: str,
    run_dir: Path,
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Enrich artifact read declarations with ``resolved_uri`` / ``resolved_path`` when known."""
    resolved: list[dict[str, Any]] = []
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        entry = deepcopy(item)
        if entry.get("from") != "nearest_sealed_ancestor":
            resolved.append(entry)
            continue
        qual = entry.get("artifact")
        if not isinstance(qual, str):
            resolved.append(entry)
            continue
        match = resolve_nearest_sealed_ancestor_artifact(
            snapshot,
            qualified_ref=qual,
            from_visit_id=visit_id,
            run_dir=run_dir,
        )
        if match:
            entry["resolved_uri"] = match["resolved_uri"]
            entry["resolved_path"] = match["resolved_path"]
        else:
            state_path = state.get("presentation_artifact_path")
            if (
                qual == "shape.present.presentation"
                and isinstance(state_path, str)
                and state_path.startswith("run:")
            ):
                entry["resolved_uri"] = state_path
                entry["resolved_path"] = str(resolve_run_uri(state_path, run_dir, visit_id))
        resolved.append(entry)
    return resolved
