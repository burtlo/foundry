"""Receipt sealing helpers and schema path conventions."""

from __future__ import annotations

import hashlib
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from foundry_cli.engine.lifecycle import now_iso, run_uuid
from foundry_cli.paths import resolve_run_uri, resolve_workspace_uri

RECEIPT_BASENAMES: dict[str, str] = {
    "intake-receipt.schema.json": "intake-receipt.json",
    "agent-receipt.schema.json": "agent-receipt.json",
}

RECEIPT_KINDS: dict[str, str] = {
    "intake-receipt.schema.json": "intake-receipt",
    "agent-receipt.schema.json": "agent-receipt",
}


def resolve_source_path(
    source: str,
    *,
    run_dir: Path,
    workspace: Path,
    visit_id: str,
) -> Path:
    if source.startswith("run:"):
        return resolve_run_uri(source, run_dir, visit_id)
    if source.startswith("workspace:"):
        return resolve_workspace_uri(source, workspace)
    raise ValueError(f"Unsupported source URI: {source!r}")


def sha256_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def find_artifact_declaration(node: dict[str, Any], artifact_id: str) -> dict[str, Any] | None:
    artifacts = (node.get("produces") or {}).get("artifacts") or []
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("id") == artifact_id:
            return artifact
    return None


def schema_name_from_registry(schema_ref: str) -> str:
    if schema_ref.startswith("registry:schemas/"):
        return schema_ref.removeprefix("registry:schemas/")
    return schema_ref


def _receipt_basename(schema_ref: str) -> str:
    schema_name = schema_name_from_registry(schema_ref)
    if schema_name in RECEIPT_BASENAMES:
        return RECEIPT_BASENAMES[schema_name]
    for marker, basename in RECEIPT_BASENAMES.items():
        if marker.removesuffix(".schema.json") in schema_ref:
            return basename
    return "receipt.json"


def _receipt_kind(schema_ref: str) -> str | None:
    schema_name = schema_name_from_registry(schema_ref)
    if schema_name in RECEIPT_KINDS:
        return RECEIPT_KINDS[schema_name]
    for marker, kind in RECEIPT_KINDS.items():
        if marker.removesuffix(".schema.json") in schema_ref:
            return kind
    return None


def seal_receipt_path(schema_ref: str, visit_id: str) -> str:
    return f"run:receipts/{visit_id}/{_receipt_basename(schema_ref)}"


def fill_receipt_provenance(
    receipt: dict[str, Any],
    *,
    schema_ref: str,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
) -> dict[str, Any]:
    filled = deepcopy(receipt)
    filled["schema_version"] = filled.get("schema_version", "2.2.0")
    filled["receipt_id"] = filled.get("receipt_id") or str(uuid.uuid4())
    filled["run_id"] = run_uuid(snapshot)
    filled["timestamp"] = filled.get("timestamp") or now_iso()
    kind = _receipt_kind(schema_ref)
    if kind == "intake-receipt":
        filled["step_id"] = filled.get("step_id") or str(visit["node_id"])
    if kind == "agent-receipt":
        provenance = filled.get("provenance") if isinstance(filled.get("provenance"), dict) else {}
        provenance.setdefault("source", "cli_seal")
        provenance.setdefault("cli_command", "receipt seal")
        provenance.setdefault("run_id", run_uuid(snapshot))
        provenance.setdefault("step_id", str(visit["node_id"]))
        filled["provenance"] = provenance
        filled.setdefault("recommended_next_state", str(visit["node_id"]))
    return filled
