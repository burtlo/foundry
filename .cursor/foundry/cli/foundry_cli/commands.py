"""Mutating and read CLI commands for the shape.intake vertical slice."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from foundry_cli.app_bootstrap import discover_app, init_app_manifest
from foundry_cli.app_manifest import validate_manifest
from foundry_cli.foundry_config import init_foundry_config, validate_foundry_config
from foundry_cli.command_context import CommandContext
from foundry_cli.constants import (
    CAP_ARTIFACT_PUBLISH,
    CAP_RECEIPT_LINK,
    CAP_TRANSITION,
    CAP_VISIT_STATE_PATCH,
    DEFAULT_ENTRY_NODE_ID,
    DEFAULT_FLOW_ID,
    EVENT_ARTIFACT_LINKED,
    EVENT_RECEIPT_LINKED,
    EVENT_RUN_STATUS_CHANGED,
    KIND_GATE,
    LIFECYCLE_OPENED,
    RUN_STATUS_NEW,
    RUN_STATUS_RUNNING,
)
from foundry_cli.context import assemble_context
from foundry_cli.docs import build_docs
from foundry_cli.engine import (
    RUN_UUID_KEY,
    admit_visit,
    decide_gate,
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
from foundry_cli.errors import error, from_engine_result, ok
from foundry_cli.ledger import append_event, filter_events
from foundry_cli.paths import resolve_run_uri, substitute_visit_id
from foundry_cli.registry import get_node, load_registry, normalize_receipts
from foundry_cli.run_archive import archive_run
from foundry_cli.run_store import RunStoreError, resolve_run_dir, save_snapshot
from foundry_cli.validate import validate_payload


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
    if str(visit.get("lifecycle")) != LIFECYCLE_OPENED:
        return error(
            "VISIT_NOT_OPENED",
            f"Visit lifecycle is {visit.get('lifecycle')!r}; mutating commands require {LIFECYCLE_OPENED!r}",
        )
    return None


def cmd_cli_resolve(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx
    return ok(
        registry_root=str(ctx.bundle),
        workspace=str(ctx.workspace),
        registry_source=ctx.registry_source,
        foundry_config_path=str(ctx.foundry_config_path) if ctx.foundry_config_path else None,
    )


def cmd_config_validate(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx
    result = validate_foundry_config(ctx.workspace)
    config_path = ctx.workspace / ".foundry" / "foundry.yaml"
    if result.get("ok"):
        return ok(
            valid=True,
            foundry_config_path=str(config_path),
            registry=result.get("registry"),
            flow=result.get("flow"),
            errors=[],
        )
    return error(
        "FOUNDRY_CONFIG_INVALID",
        result.get("errors", ["Foundry config validation failed"])[0],
        valid=False,
        foundry_config_path=str(config_path),
        errors=result.get("errors", []),
        flow=result.get("flow"),
    )


def cmd_config_init(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx
    registry_ref = getattr(args, "registry_path", None)
    flow = getattr(args, "flow", None)
    try:
        result = init_foundry_config(
            ctx.workspace,
            ctx.bundle,
            registry_ref=registry_ref,
            flow=flow,
            dry_run=bool(getattr(args, "dry_run", False)),
            force=bool(getattr(args, "force", False)),
        )
    except FileExistsError as exc:
        return error("FOUNDRY_CONFIG_EXISTS", str(exc), requires_force=True)
    except ValueError as exc:
        message = str(exc)
        if "validation failed" in message.lower():
            return error("FOUNDRY_CONFIG_VALIDATION_FAILED", message)
        return error("INVALID_FOUNDRY_CONFIG_INPUT", message)
    except OSError as exc:
        return error("INVALID_FOUNDRY_CONFIG_INPUT", str(exc))
    return ok(**result)


def cmd_run_create(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    flow_id = args.flow or DEFAULT_FLOW_ID
    try:
        _, flow = load_registry(ctx.bundle, flow_id=flow_id)
    except ValueError as exc:
        return error("INVALID_FLOW", str(exc))

    entry_node_id = str(flow.get("entry", DEFAULT_ENTRY_NODE_ID))
    manifest = validate_manifest(ctx.workspace, ctx.bundle)
    manifest_id = manifest.get("manifest_id") if isinstance(manifest.get("manifest_id"), str) else None
    run_id = getattr(args, "run_id", None) or generate_run_slug(ctx.workspace, manifest_id)
    run_dir = ctx.workspace / ".foundry" / "runs" / run_id
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
        "status": RUN_STATUS_RUNNING,
        "workspace": str(ctx.workspace),
        "config": {"workspace": str(ctx.workspace)},
        "state": {"ticket": None, "app_folder": None},
        "visits": [],
        "ledger": [],
    }

    append_event(
        snapshot,
        event_type=EVENT_RUN_STATUS_CHANGED,
        payload={"prior_status": RUN_STATUS_NEW, "new_status": RUN_STATUS_RUNNING},
    )

    visit = admit_visit(
        snapshot,
        node_id=entry_node_id,
        flow=flow,
        source="entry",
        workspace=ctx.workspace,
        foundry_bundle=ctx.bundle,
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


def cmd_run_context(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    loaded = ctx.load_run(args)
    if isinstance(loaded, dict):
        return loaded
    run_dir, snapshot, visit, flow = loaded

    try:
        get_node(flow, str(visit["node_id"]))
    except KeyError as exc:
        return error("NODE_NOT_FOUND", f"Node not found in flow registry: {exc.args[0]}")

    try:
        context = assemble_context(
            snapshot=snapshot,
            visit=visit,
            flow=flow,
            foundry_bundle=ctx.bundle,
            run_dir=run_dir,
            workspace=ctx.workspace,
        )
    except ValueError as exc:
        return error("INVALID_NODE", str(exc))

    schema_errors = validate_payload(context, "context-packet.schema.json", ctx.bundle)
    if schema_errors:
        return error("SCHEMA_VALIDATION_FAILED", "; ".join(schema_errors))

    return ok(context=context)


def cmd_run_archive(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    try:
        run_dir = resolve_run_dir(
            run_id=getattr(args, "run", None),
            run_dir=Path(args.run_dir).resolve() if getattr(args, "run_dir", None) else None,
            workspace=ctx.workspace,
        )
    except RunStoreError as exc:
        return error(exc.code, exc.message)

    archive_root = Path(args.archive_root).resolve() if getattr(args, "archive_root", None) else None
    transcript = Path(args.transcript).resolve() if getattr(args, "transcript", None) else None
    review = Path(args.review_file).resolve() if getattr(args, "review_file", None) else None
    archive_slug = getattr(args, "archive_slug", None)

    try:
        result = archive_run(
            source_run_dir=run_dir,
            foundry_bundle=ctx.bundle,
            archive_root=archive_root,
            archive_slug=archive_slug,
            transcript_path=transcript,
            review_path=review,
            dry_run=bool(getattr(args, "dry_run", False)),
            remove_source=not bool(getattr(args, "copy", False)),
        )
    except FileNotFoundError as exc:
        return error("ARCHIVE_INPUT_NOT_FOUND", str(exc))
    except FileExistsError as exc:
        return error("ARCHIVE_EXISTS", str(exc))
    except ValueError as exc:
        return error("INVALID_ARCHIVE_INPUT", str(exc))

    return ok(**result)


def cmd_doc_build(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    flow_id = args.flow or DEFAULT_FLOW_ID
    output_dir = Path(args.output).resolve() if args.output else None
    return build_docs(
        workspace=ctx.workspace,
        bundle=ctx.bundle,
        flow_id=flow_id,
        node_id=args.node,
        output_dir=output_dir,
    )


def cmd_visit_state_patch(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    loaded = ctx.load_run(args)
    if isinstance(loaded, dict):
        return loaded
    run_dir, snapshot, visit, flow = loaded

    node = get_node(flow, str(visit["node_id"]))
    denied = _require_capability(node, CAP_VISIT_STATE_PATCH)
    if denied:
        return denied
    not_open = _require_opened(visit)
    if not_open:
        return not_open

    if args.file:
        patch_path = resolve_source_path(args.file, run_dir=run_dir, workspace=ctx.workspace, visit_id=str(visit["id"]))
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
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    loaded = ctx.load_run(args)
    if isinstance(loaded, dict):
        return loaded
    _, snapshot, _, _ = loaded

    types = [item.strip() for item in (args.types or "").split(",") if item.strip()] or None
    from_seq = int(args.from_seq) if args.from_seq else None
    to_seq = int(args.to_seq) if args.to_seq else None
    events = filter_events(snapshot, from_seq=from_seq, to_seq=to_seq, types=types)
    return ok(run_id=str(snapshot.get("run_id")), events=events, truncated=False)


def cmd_artifact_publish(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    loaded = ctx.load_run(args)
    if isinstance(loaded, dict):
        return loaded
    run_dir, snapshot, visit, flow = loaded

    node = get_node(flow, str(visit["node_id"]))
    denied = _require_capability(node, CAP_ARTIFACT_PUBLISH)
    if denied:
        return denied
    not_open = _require_opened(visit)
    if not_open:
        return not_open

    artifact_decl = find_artifact_declaration(node, args.artifact)
    if artifact_decl is None:
        return error("ARTIFACT_NOT_DECLARED", f"Artifact {args.artifact!r} not declared on {visit['node_id']!r}")

    visit_id = str(visit["id"])
    source_path = resolve_source_path(args.source, run_dir=run_dir, workspace=ctx.workspace, visit_id=visit_id)
    if not source_path.is_file():
        return error("SOURCE_NOT_FOUND", f"Source file not found: {source_path}")

    declared_uri = substitute_visit_id(str(artifact_decl.get("uri", "")), visit_id)
    dest_path = resolve_run_uri(declared_uri, run_dir, visit_id)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    source_text = source_path.read_text(encoding="utf-8")
    schema_ref = str(artifact_decl.get("schema", ""))
    artifact_kind = str(artifact_decl.get("kind", ""))
    payload: dict[str, Any] | None = None
    if schema_ref:
        try:
            parsed = json.loads(source_text)
        except json.JSONDecodeError as exc:
            return error("INVALID_REQUEST", f"Artifact source is not valid JSON: {exc}")
        if not isinstance(parsed, dict):
            return error("INVALID_REQUEST", "Artifact source JSON must be an object")
        payload = parsed
        schema_errors = validate_payload(payload, schema_name_from_registry(schema_ref), ctx.bundle)
        if schema_errors:
            return error("SCHEMA_VALIDATION_FAILED", "; ".join(schema_errors))
        shutil.copy2(source_path, dest_path)
    elif artifact_kind == "document":
        dest_path.write_text(source_text, encoding="utf-8")
    else:
        shutil.copy2(source_path, dest_path)
    digest = sha256_digest(dest_path)

    event = append_event(
        snapshot,
        event_type=EVENT_ARTIFACT_LINKED,
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
    if isinstance(state, dict) and args.artifact == "ticket" and payload is not None:
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
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    loaded = ctx.load_run(args)
    if isinstance(loaded, dict):
        return loaded
    run_dir, snapshot, visit, flow = loaded

    node = get_node(flow, str(visit["node_id"]))
    denied = _require_capability(node, CAP_RECEIPT_LINK)
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
    source_path = resolve_source_path(args.file, run_dir=run_dir, workspace=ctx.workspace, visit_id=visit_id)
    if not source_path.is_file():
        return error("SOURCE_NOT_FOUND", f"Receipt draft not found: {source_path}")

    draft = json.loads(source_path.read_text(encoding="utf-8"))
    sealed = fill_receipt_provenance(draft, schema_ref=schema_ref, snapshot=snapshot, visit=visit)
    schema_errors = validate_payload(sealed, schema_name_from_registry(schema_ref), ctx.bundle)
    if schema_errors:
        return error("SCHEMA_VALIDATION_FAILED", "; ".join(schema_errors))

    sealed_uri = seal_receipt_path(schema_ref, visit_id)
    sealed_path = resolve_run_uri(sealed_uri, run_dir, visit_id)
    sealed_path.parent.mkdir(parents=True, exist_ok=True)
    sealed_path.write_text(json.dumps(sealed, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    event = append_event(
        snapshot,
        event_type=EVENT_RECEIPT_LINKED,
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


def cmd_gate_decide(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    loaded = ctx.load_run(args)
    if isinstance(loaded, dict):
        return loaded
    run_dir, snapshot, visit, flow = loaded

    decision = getattr(args, "decision", None)
    if not decision:
        return error("DECISION_REQUIRED", "Provide --decision")

    result = decide_gate(
        snapshot,
        visit,
        flow,
        decision=str(decision),
        workspace=ctx.workspace,
        foundry_bundle=ctx.bundle,
        run_dir=run_dir,
    )
    save_snapshot(run_dir, snapshot)
    return from_engine_result(result)


def cmd_visit_transition(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    loaded = ctx.load_run(args)
    if isinstance(loaded, dict):
        return loaded
    run_dir, snapshot, visit, flow = loaded

    node = get_node(flow, str(visit["node_id"]))
    if str(visit.get("kind")) == KIND_GATE or str(node.get("kind")) == KIND_GATE:
        return error(
            "GATE_USE_DECIDE",
            "Gate visits close via gate decide, not visit transition",
        )

    denied = _require_capability(node, CAP_TRANSITION)
    if denied:
        return denied

    result = transition_visit(
        snapshot,
        visit,
        flow,
        workspace=ctx.workspace,
        foundry_bundle=ctx.bundle,
        run_dir=run_dir,
        summary=getattr(args, "summary", None),
    )
    save_snapshot(run_dir, snapshot)
    return from_engine_result(result)


def cmd_app_discover(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args, require_registry=False)
    if isinstance(ctx, dict):
        return ctx
    try:
        result = discover_app(ctx.workspace)
    except ValueError as exc:
        return error("INVALID_WORKSPACE", str(exc))
    return ok(**result)


def cmd_app_init(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx
    manifest_file = getattr(args, "manifest_file", None)
    if not manifest_file:
        return error("INVALID_REQUEST", "--manifest-file is required for app init")
    try:
        result = init_app_manifest(
            ctx.workspace,
            Path(manifest_file),
            ctx.bundle,
            dry_run=bool(getattr(args, "dry_run", False)),
            force=bool(getattr(args, "force", False)),
        )
    except FileExistsError as exc:
        return error("APP_MANIFEST_EXISTS", str(exc), requires_force=True)
    except ValueError as exc:
        message = str(exc)
        if "Git ignore rules hide" in message:
            return error("APP_MANIFEST_GITIGNORE_BLOCKED", message)
        if "Manifest validation failed" in message:
            return error("APP_MANIFEST_VALIDATION_FAILED", message)
        return error("INVALID_MANIFEST_INPUT", message)
    except OSError as exc:
        return error("INVALID_MANIFEST_INPUT", str(exc))
    return ok(**result)


def cmd_app_validate(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx
    manifest_override = getattr(args, "manifest", None)
    if manifest_override:
        try:
            from foundry_cli.app_bootstrap import _load_yaml_mapping, validate_manifest_data

            path = Path(manifest_override).resolve()
            data = _load_yaml_mapping(path, "Application manifest")
            errors = validate_manifest_data(data, ctx.bundle)
            if errors:
                return error(
                    "APP_MANIFEST_INVALID",
                    errors[0],
                    valid=False,
                    manifest_path=str(path),
                    errors=errors,
                    manifest_id=data.get("id"),
                )
            return ok(
                valid=True,
                manifest_path=str(path),
                manifest_id=data.get("id"),
                errors=[],
            )
        except (ValueError, OSError) as exc:
            return error("APP_MANIFEST_INVALID", str(exc), valid=False)
    result = validate_manifest(ctx.workspace, ctx.bundle)
    if result.get("ok"):
        return ok(valid=True, manifest_path=str(ctx.workspace / ".foundry" / "app.yaml"), **result)
    return error(
        "APP_MANIFEST_INVALID",
        result.get("errors", ["Manifest validation failed"])[0],
        valid=False,
        manifest_path=str(ctx.workspace / ".foundry" / "app.yaml"),
        errors=result.get("errors", []),
        manifest_id=result.get("manifest_id"),
    )
