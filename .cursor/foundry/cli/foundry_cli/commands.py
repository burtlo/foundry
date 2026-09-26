"""Mutating and read CLI commands for the shape.intake vertical slice."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from foundry_cli.app_manifest import validate_manifest
from foundry_cli.engine import (
    RUN_UUID_KEY,
    active_visit,
    admit_visit,
    fill_receipt_provenance,
    find_artifact_declaration,
    generate_run_slug,
    patch_allowed,
    resolve_source_path,
    schema_name_from_registry,
    seal_receipt_path,
    sha256_digest,
    transition_visit,
)
from foundry_cli.errors import error, ok
from foundry_cli.ledger import append_event, filter_events
from foundry_cli.paths import foundry_root, resolve_run_uri, substitute_visit_id
from foundry_cli.registry import get_node, load_registry, normalize_receipts
from foundry_cli.run_store import RunStoreError, load_snapshot, resolve_run_dir, save_snapshot, select_visit
from foundry_cli.validate import validate_payload

CAPABILITY_COMMANDS = {
    "visit.state_patch": "visit state patch",
    "ledger.show": "ledger show",
    "artifact.publish": "artifact publish",
    "receipt.link": "receipt seal",
    "transition": "visit transition",
}


def _bundle(args: argparse.Namespace, workspace: Path) -> Path:
    return Path(args.registry).resolve() if args.registry else foundry_root(workspace)


def _run_context(args: argparse.Namespace, workspace: Path) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    bundle = _bundle(args, workspace)
    run_dir = resolve_run_dir(
        run_id=getattr(args, "run", None),
        run_dir=Path(args.run_dir).resolve() if getattr(args, "run_dir", None) else None,
        workspace=workspace,
    )
    snapshot = load_snapshot(run_dir)
    visit = select_visit(snapshot, getattr(args, "visit", None))
    flow_id = getattr(args, "flow", None) or str(snapshot.get("flow_id") or "implementation")
    _, flow = load_registry(bundle, flow_id=flow_id)
    return run_dir, snapshot, visit, flow


def _require_capability(node: dict[str, Any], capability: str) -> dict[str, Any] | None:
    allow = node.get("allow") or {}
    cli_caps = allow.get("cli") or []
    if capability not in cli_caps:
        return error(
            "CAPABILITY_DENIED",
            f"Capability {capability!r} not allowed on node {node.get('id')!r}",
        )
    return None


def _require_opened(visit: dict[str, Any]) -> dict[str, Any] | None:
    if str(visit.get("lifecycle")) != "opened":
        return error(
            "VISIT_NOT_OPENED",
            f"Visit lifecycle is {visit.get('lifecycle')!r}; mutating commands require 'opened'",
        )
    return None


def cmd_cli_resolve(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace).resolve()
    try:
        bundle = _bundle(args, workspace)
    except FileNotFoundError as exc:
        return error("REGISTRY_NOT_FOUND", str(exc))
    return ok(registry_root=str(bundle), workspace=str(workspace))


def cmd_run_create(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace).resolve()
    try:
        bundle = _bundle(args, workspace)
    except FileNotFoundError as exc:
        return error("REGISTRY_NOT_FOUND", str(exc))

    flow_id = args.flow or "implementation"
    try:
        _, flow = load_registry(bundle, flow_id=flow_id)
    except ValueError as exc:
        return error("INVALID_FLOW", str(exc))

    entry_node_id = str(flow.get("entry", "shape.intake"))
    manifest = validate_manifest(workspace, bundle)
    manifest_id = manifest.get("manifest_id") if isinstance(manifest.get("manifest_id"), str) else None
    run_id = getattr(args, "run_id", None) or generate_run_slug(workspace, manifest_id)
    run_dir = workspace / ".foundry" / "runs" / run_id
    if run_dir.exists():
        return error("RUN_EXISTS", f"Run directory already exists: {run_dir}")

    run_dir.mkdir(parents=True)
    (run_dir / "artifacts").mkdir(exist_ok=True)
    (run_dir / "receipts").mkdir(exist_ok=True)

    snapshot: dict[str, Any] = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        RUN_UUID_KEY: str(uuid.uuid4()),
        "flow_id": flow_id,
        "status": "running",
        "workspace": str(workspace),
        "config": {"workspace": str(workspace)},
        "state": {"ticket": None, "app_folder": None},
        "visits": [],
        "ledger": [],
    }

    append_event(
        snapshot,
        event_type="run.status_changed",
        payload={"prior_status": "new", "new_status": "running"},
    )

    visit = admit_visit(
        snapshot,
        node_id=entry_node_id,
        flow=flow,
        source="entry",
        workspace=workspace,
        foundry_bundle=bundle,
        run_dir=run_dir,
    )
    snapshot["active_visit"] = visit
    save_snapshot(run_dir, snapshot)

    return ok(
        run_id=run_id,
        flow_id=flow_id,
        status=str(snapshot.get("status")),
        entry_node_id=entry_node_id,
        active_visit_id=visit.get("id"),
        active_lifecycle=visit.get("lifecycle"),
        run_dir=str(run_dir),
    )


def cmd_visit_state_patch(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace).resolve()
    try:
        bundle = _bundle(args, workspace)
        run_dir, snapshot, visit, flow = _run_context(args, workspace)
    except RunStoreError as exc:
        return error(exc.code, exc.message)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        return error("INVALID_REQUEST", str(exc))

    node = get_node(flow, str(visit["node_id"]))
    denied = _require_capability(node, "visit.state_patch")
    if denied:
        return denied
    not_open = _require_opened(visit)
    if not_open:
        return not_open

    if args.file:
        patch_path = resolve_source_path(args.file, run_dir=run_dir, workspace=workspace, visit_id=str(visit["id"]))
        patch = json.loads(patch_path.read_text(encoding="utf-8"))
    elif args.set:
        patch = json.loads(args.set)
    else:
        return error("INVALID_PATCH", "Provide --set or --file")

    if not isinstance(patch, dict):
        return error("INVALID_PATCH", "Patch must be a JSON object")

    patched, rejected = patch_allowed(snapshot, node, str(visit["node_id"]), patch)
    if rejected and not patched:
        return error("STATE_PATCH_DENIED", f"Rejected paths: {', '.join(rejected)}")

    save_snapshot(run_dir, snapshot)
    return ok(
        visit_id=visit.get("id"),
        node_id=visit.get("node_id"),
        lifecycle=visit.get("lifecycle"),
        patched_paths=patched,
        rejected_paths=rejected,
    )


def cmd_ledger_show(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace).resolve()
    try:
        run_dir, snapshot, _, _ = _run_context(args, workspace)
    except RunStoreError as exc:
        return error(exc.code, exc.message)

    types = [item.strip() for item in (args.types or "").split(",") if item.strip()] or None
    from_seq = int(args.from_seq) if args.from_seq else None
    to_seq = int(args.to_seq) if args.to_seq else None
    events = filter_events(snapshot, from_seq=from_seq, to_seq=to_seq, types=types)
    return ok(run_id=str(snapshot.get("run_id")), events=events, truncated=False)


def cmd_artifact_publish(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace).resolve()
    try:
        bundle = _bundle(args, workspace)
        run_dir, snapshot, visit, flow = _run_context(args, workspace)
    except RunStoreError as exc:
        return error(exc.code, exc.message)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        return error("INVALID_REQUEST", str(exc))

    node = get_node(flow, str(visit["node_id"]))
    denied = _require_capability(node, "artifact.publish")
    if denied:
        return denied
    not_open = _require_opened(visit)
    if not_open:
        return not_open

    artifact_decl = find_artifact_declaration(node, args.artifact)
    if artifact_decl is None:
        return error("ARTIFACT_NOT_DECLARED", f"Artifact {args.artifact!r} not declared on {visit['node_id']!r}")

    visit_id = str(visit["id"])
    source_path = resolve_source_path(args.source, run_dir=run_dir, workspace=workspace, visit_id=visit_id)
    if not source_path.is_file():
        return error("SOURCE_NOT_FOUND", f"Source file not found: {source_path}")

    declared_uri = substitute_visit_id(str(artifact_decl.get("uri", "")), visit_id)
    dest_path = resolve_run_uri(declared_uri, run_dir, visit_id)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.loads(source_path.read_text(encoding="utf-8"))
    schema_ref = str(artifact_decl.get("schema", ""))
    if schema_ref:
        schema_errors = validate_payload(payload, schema_name_from_registry(schema_ref), bundle)
        if schema_errors:
            return error("SCHEMA_VALIDATION_FAILED", "; ".join(schema_errors))

    shutil.copy2(source_path, dest_path)
    digest = sha256_digest(dest_path)

    event = append_event(
        snapshot,
        event_type="artifact.linked",
        visit_id=visit_id,
        node_id=str(visit["node_id"]),
        payload={
            "artifact_id": args.artifact,
            "uri": declared_uri,
            "schema": schema_ref,
            "media_type": artifact_decl.get("media_type"),
            "digest": digest,
        },
    )
    state = snapshot.setdefault("state", {})
    if isinstance(state, dict) and args.artifact == "ticket":
        state["ticket"] = payload

    save_snapshot(run_dir, snapshot)
    return ok(
        artifact={
            "id": args.artifact,
            "kind": artifact_decl.get("kind"),
            "producer_node_id": visit["node_id"],
            "producer_visit_id": visit_id,
            "uri": declared_uri,
            "schema": schema_ref,
            "media_type": artifact_decl.get("media_type"),
            "digest": digest,
        },
        ledger_seq=event.get("seq"),
    )


def cmd_receipt_seal(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace).resolve()
    try:
        bundle = _bundle(args, workspace)
        run_dir, snapshot, visit, flow = _run_context(args, workspace)
    except RunStoreError as exc:
        return error(exc.code, exc.message)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        return error("INVALID_REQUEST", str(exc))

    node = get_node(flow, str(visit["node_id"]))
    denied = _require_capability(node, "receipt.link")
    if denied:
        return denied
    not_open = _require_opened(visit)
    if not_open:
        return not_open

    schema_ref = args.schema
    if not schema_ref:
        receipts = normalize_receipts(node)
        if len(receipts) != 1:
            return error("SCHEMA_REQUIRED", "Provide --schema when node declares multiple receipt schemas")
        schema_ref = receipts[0]

    allowed_schemas = set(normalize_receipts(node))
    if schema_ref not in allowed_schemas:
        return error("SCHEMA_NOT_ALLOWED", f"Schema {schema_ref!r} not declared on node {visit['node_id']!r}")

    visit_id = str(visit["id"])
    source_path = resolve_source_path(args.file, run_dir=run_dir, workspace=workspace, visit_id=visit_id)
    if not source_path.is_file():
        return error("SOURCE_NOT_FOUND", f"Receipt draft not found: {source_path}")

    draft = json.loads(source_path.read_text(encoding="utf-8"))
    sealed = fill_receipt_provenance(draft, schema_ref=schema_ref, snapshot=snapshot, visit=visit)
    schema_errors = validate_payload(sealed, schema_name_from_registry(schema_ref), bundle)
    if schema_errors:
        return error("SCHEMA_VALIDATION_FAILED", "; ".join(schema_errors))

    sealed_uri = seal_receipt_path(schema_ref, visit_id)
    sealed_path = resolve_run_uri(sealed_uri, run_dir, visit_id)
    sealed_path.parent.mkdir(parents=True, exist_ok=True)
    sealed_path.write_text(json.dumps(sealed, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    event = append_event(
        snapshot,
        event_type="receipt.linked",
        visit_id=visit_id,
        node_id=str(visit["node_id"]),
        payload={
            "receipt_id": sealed.get("receipt_id"),
            "path": sealed_uri,
            "schema": schema_ref,
        },
    )
    save_snapshot(run_dir, snapshot)
    return ok(
        receipt_id=sealed.get("receipt_id"),
        path=sealed_uri,
        schema=schema_ref,
        visit_id=visit_id,
        node_id=visit.get("node_id"),
        ledger_seq=event.get("seq"),
    )


def cmd_visit_transition(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace).resolve()
    try:
        bundle = _bundle(args, workspace)
        run_dir, snapshot, visit, flow = _run_context(args, workspace)
    except RunStoreError as exc:
        return error(exc.code, exc.message)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        return error("INVALID_REQUEST", str(exc))

    node = get_node(flow, str(visit["node_id"]))
    denied = _require_capability(node, "transition")
    if denied:
        return denied

    result = transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=bundle,
        run_dir=run_dir,
        summary=getattr(args, "summary", None),
    )
    save_snapshot(run_dir, snapshot)

    if not result.get("ok"):
        return error(
            str(result.get("code", "TRANSITION_FAILED")),
            str(result.get("message", "Transition failed")),
            **{k: v for k, v in result.items() if k not in {"ok", "code", "message"}},
        )
    return ok(**{k: v for k, v in result.items() if k != "ok"})
