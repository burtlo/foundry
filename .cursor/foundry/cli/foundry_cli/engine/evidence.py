"""Ledger-linked receipt and sealed-step evidence read model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from foundry_cli.ledger import last_event, ledger_events
from foundry_cli.paths import resolve_run_uri

AGENT_RECEIPT_SCHEMA = "registry:schemas/agent-receipt.schema.json"
INTAKE_RECEIPT_SCHEMA = "registry:schemas/intake-receipt.schema.json"


def sealed_step_visit_id(snapshot: dict[str, Any], node_id: str) -> str | None:
    event = last_event(snapshot, "visit.sealed", node_id=node_id)
    if event is None:
        return None
    visit_id = event.get("visit_id")
    return str(visit_id) if visit_id else None


def load_linked_receipt(
    snapshot: dict[str, Any],
    visit_id: str,
    schema: str,
    run_dir: Path,
) -> dict[str, Any] | None:
    for event in reversed(ledger_events(snapshot)):
        if not isinstance(event, dict) or event.get("type") != "receipt.linked":
            continue
        if event.get("visit_id") != visit_id:
            continue
        payload = event.get("payload") or {}
        if payload.get("schema") != schema:
            continue
        path_uri = payload.get("path")
        if not isinstance(path_uri, str):
            return None
        receipt_path = resolve_run_uri(path_uri, run_dir, visit_id)
        if not receipt_path.is_file():
            return {"_missing_file": str(receipt_path)}
        return json.loads(receipt_path.read_text(encoding="utf-8"))
    return None


def load_linked_artifact(
    snapshot: dict[str, Any],
    visit_id: str,
    artifact_id: str,
    run_dir: Path,
) -> dict[str, Any] | None:
    for event in reversed(ledger_events(snapshot)):
        if not isinstance(event, dict) or event.get("type") != "artifact.linked":
            continue
        if event.get("visit_id") != visit_id:
            continue
        payload = event.get("payload") or {}
        if payload.get("artifact_id") != artifact_id:
            continue
        path_uri = payload.get("uri")
        if not isinstance(path_uri, str):
            return None
        artifact_path = resolve_run_uri(path_uri, run_dir, visit_id)
        if not artifact_path.is_file():
            return {"_missing_file": str(artifact_path)}
        return json.loads(artifact_path.read_text(encoding="utf-8"))
    return None


def _sealed_step_facts(snapshot: dict[str, Any], step_node_id: str) -> dict[str, Any]:
    event = last_event(snapshot, "visit.sealed", node_id=step_node_id)
    visit_id = event.get("visit_id") if event is not None else None
    payload = (event.get("payload") if event is not None else None) or {}
    return {
        "step": step_node_id,
        "sealed": bool(visit_id),
        "visit_id": str(visit_id) if visit_id else None,
        "outcome": payload.get("outcome") if isinstance(payload, dict) else None,
        "linked": False,
        "missing_file": None,
    }


def _receipt_evidence(
    snapshot: dict[str, Any], spec: dict[str, Any], run_dir: Path
) -> dict[str, Any]:
    facts = _sealed_step_facts(snapshot, str(spec["step"]))
    facts.update(
        receipt_id=None,
        status=None,
        commands_count=0,
        commands_all_pass=False,
        commands_any_failed=False,
    )
    if not facts["sealed"]:
        return facts
    receipt = load_linked_receipt(snapshot, facts["visit_id"], str(spec["schema"]), run_dir)
    if receipt is None:
        return facts
    facts["linked"] = True
    if receipt.get("_missing_file"):
        facts["missing_file"] = receipt["_missing_file"]
        return facts
    receipt_id = receipt.get("receipt_id")
    commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []
    facts.update(
        receipt_id=str(receipt_id) if receipt_id else None,
        status=str(receipt.get("status") or ""),
        commands_count=len(commands),
        commands_all_pass=bool(commands)
        and all(isinstance(item, dict) and item.get("exit_code", 1) == 0 for item in commands),
        commands_any_failed=any(
            isinstance(item, dict) and item.get("exit_code", 0) != 0 for item in commands
        ),
    )
    return facts


_FIELD_TRANSFORMS = {
    "trim_lower": lambda value: None if value is None else str(value).strip().lower(),
}


def _artifact_evidence(
    snapshot: dict[str, Any], spec: dict[str, Any], run_dir: Path
) -> dict[str, Any]:
    facts = _sealed_step_facts(snapshot, str(spec["step"]))
    fields = spec.get("fields") or {}
    facts.update({name: None for name in fields})
    if not facts["sealed"]:
        return facts
    artifact = load_linked_artifact(snapshot, facts["visit_id"], str(spec["artifact_id"]), run_dir)
    if artifact is None:
        return facts
    facts["linked"] = True
    if artifact.get("_missing_file"):
        facts["missing_file"] = artifact["_missing_file"]
        return facts
    for name, field_spec in fields.items():
        if isinstance(field_spec, str):
            field_spec = {"path": field_spec}
        value = artifact.get(str(field_spec.get("path") or name))
        transform = field_spec.get("transform")
        if transform:
            value = _FIELD_TRANSFORMS[str(transform)](value)
        facts[name] = value
    return facts


def _state_evidence(snapshot: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    state = snapshot.get("state")
    field = str(spec["field"])
    present = isinstance(state, dict) and field in state
    return {"present": present, "value": state.get(field) if present else None}


def gate_evidence(
    snapshot: dict[str, Any],
    specs: dict[str, dict[str, Any]],
    run_dir: Path,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Load declared gate evidence; returns facts by evidence id and receipt refs."""
    facts: dict[str, dict[str, Any]] = {}
    refs: list[str] = []
    for evidence_id, spec in specs.items():
        kind = str(spec.get("kind") or "")
        if kind == "receipt":
            item = _receipt_evidence(snapshot, spec, run_dir)
            if item.get("receipt_id"):
                refs.append(str(item["receipt_id"]))
        elif kind == "artifact":
            item = _artifact_evidence(snapshot, spec, run_dir)
        elif kind == "state":
            item = _state_evidence(snapshot, spec)
        else:
            raise ValueError(f"Unknown gate evidence kind {kind!r} for {evidence_id!r}")
        facts[evidence_id] = item
    return facts, refs


def _linked_receipt_path_uri(
    snapshot: dict[str, Any],
    visit_id: str,
    schema: str,
) -> str | None:
    for event in reversed(ledger_events(snapshot)):
        if not isinstance(event, dict) or event.get("type") != "receipt.linked":
            continue
        if event.get("visit_id") != visit_id:
            continue
        payload = event.get("payload") or {}
        if payload.get("schema") != schema:
            continue
        path_uri = payload.get("path")
        if isinstance(path_uri, str):
            return path_uri
    return None


def intake_receipt_summary(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
    step_node_id: str,
) -> dict[str, Any] | None:
    intake_visit_id = sealed_step_visit_id(snapshot, step_node_id)
    if not intake_visit_id:
        return None
    receipt = load_linked_receipt(snapshot, intake_visit_id, INTAKE_RECEIPT_SCHEMA, run_dir)
    if receipt is None:
        return {"visit_id": intake_visit_id, "status": None, "receipt_id": None, "resolved_path": None}
    if receipt.get("_missing_file"):
        return {
            "visit_id": intake_visit_id,
            "status": None,
            "receipt_id": None,
            "resolved_path": None,
            "missing_file": receipt["_missing_file"],
        }
    receipt_id = receipt.get("receipt_id")
    path_uri = _linked_receipt_path_uri(snapshot, intake_visit_id, INTAKE_RECEIPT_SCHEMA)
    resolved_path = None
    if path_uri is not None:
        resolved_path = str(resolve_run_uri(path_uri, run_dir, intake_visit_id))
    return {
        "visit_id": intake_visit_id,
        "status": str(receipt.get("status") or ""),
        "receipt_id": str(receipt_id) if receipt_id else None,
        "resolved_path": resolved_path,
    }


def agent_receipt_summary(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
    step_node_id: str,
) -> dict[str, Any] | None:
    test_visit_id = sealed_step_visit_id(snapshot, step_node_id)
    if not test_visit_id:
        return None
    receipt = load_linked_receipt(snapshot, test_visit_id, AGENT_RECEIPT_SCHEMA, run_dir)
    if receipt is None:
        return {
            "visit_id": test_visit_id,
            "status": None,
            "receipt_id": None,
            "resolved_path": None,
            "commands": [],
        }
    if receipt.get("_missing_file"):
        return {
            "visit_id": test_visit_id,
            "status": None,
            "receipt_id": None,
            "resolved_path": None,
            "missing_file": receipt["_missing_file"],
            "commands": [],
        }
    receipt_id = receipt.get("receipt_id")
    path_uri = _linked_receipt_path_uri(snapshot, test_visit_id, AGENT_RECEIPT_SCHEMA)
    resolved_path = None
    if path_uri is not None:
        resolved_path = str(resolve_run_uri(path_uri, run_dir, test_visit_id))
    raw_commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []
    commands: list[dict[str, Any]] = []
    for item in raw_commands:
        if not isinstance(item, dict):
            continue
        commands.append(
            {
                "command": str(item.get("command") or ""),
                "exit_code": int(item.get("exit_code", 1)),
            }
        )
    return {
        "visit_id": test_visit_id,
        "status": str(receipt.get("status") or ""),
        "receipt_id": str(receipt_id) if receipt_id else None,
        "resolved_path": resolved_path,
        "commands": commands,
    }
