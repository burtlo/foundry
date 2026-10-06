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
from foundry_cli.paths import resolve_cli_path
from foundry_cli.constants import (
    CAP_ARTIFACT_PUBLISH,
    CAP_RECEIPT_LINK,
    CAP_TRANSITION,
    CAP_RUN_AGENT_SUBMIT,
    CAP_VISIT_EXAMINE_COMPLETE,
    CAP_VISIT_INTAKE_COMPLETE,
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
from foundry_cli.engine.examination_state import sync_open_clarifying_questions_count
from foundry_cli.engine.intake_executor import run_shape_intake_complete
from foundry_cli.engine.shape_step_executor import run_shape_examine_complete
from foundry_cli.errors import error, from_engine_result, ok
from foundry_cli.ledger import append_event, filter_events
from foundry_cli.paths import resolve_run_uri, substitute_visit_id
from foundry_cli.registry import get_node, load_registry, normalize_receipts
from foundry_cli.engine.wait_state import clear_run_wait
from foundry_cli.host.client import call_host
from foundry_cli.host.discovery import host_is_running
from foundry_cli.run_service import (
    advance_run_durable,
    create_run,
    get_run,
    list_runs,
    run_events,
    submit_agent_result_durable,
)
from foundry_cli.run_archive import archive_run
from foundry_cli.run_store import (
    REVISION_KEY,
    RunStoreError,
    commit_snapshot,
    get_revision,
    load_snapshot,
    resolve_run_dir,
    save_snapshot,
)
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


def _parse_expected_revision(args: argparse.Namespace) -> int | None:
    raw = getattr(args, "revision", None)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return -1


def _persist_run(
    run_dir: Path,
    snapshot: dict[str, Any],
    args: argparse.Namespace,
    *,
    bump: bool = True,
) -> dict[str, Any] | None:
    expected = _parse_expected_revision(args)
    if expected == -1:
        return error("INVALID_REVISION", "revision must be an integer")
    try:
        revision = commit_snapshot(
            run_dir,
            snapshot,
            expected_revision=expected,
            bump=bump,
        )
    except RunStoreError as exc:
        if exc.code == "STALE_REVISION":
            try:
                current = get_revision(load_snapshot(run_dir))
            except RunStoreError:
                current = None
            return error(
                exc.code,
                exc.message,
                revision=current,
            )
        return error(exc.code, exc.message)
    snapshot[REVISION_KEY] = revision
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
        cli_path=resolve_cli_path(ctx.bundle, ctx.workspace),
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

    work_prompt = getattr(args, "work_prompt", None)
    return create_run(
        workspace=ctx.workspace,
        bundle=ctx.bundle,
        work_prompt=work_prompt if isinstance(work_prompt, str) else None,
        flow_id=getattr(args, "flow", None),
        run_id=getattr(args, "run_id", None),
    )


def cmd_run_get(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx
    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        return call_host(
            ctx.workspace,
            "run.get",
            {
                "run_id": getattr(args, "run", None),
                "run_dir": getattr(args, "run_dir", None),
            },
        )
    return get_run(
        ctx.workspace,
        run_id=getattr(args, "run", None),
        run_dir=Path(args.run_dir).resolve() if getattr(args, "run_dir", None) else None,
    )


def cmd_run_list(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx
    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        return call_host(ctx.workspace, "run.list", {})
    return list_runs(ctx.workspace)


def cmd_run_events(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx
    after_seq = int(getattr(args, "after_seq", None) or 0)
    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        return call_host(
            ctx.workspace,
            "run.events",
            {
                "run_id": getattr(args, "run", None),
                "run_dir": getattr(args, "run_dir", None),
                "after_seq": after_seq,
            },
        )
    return run_events(
        ctx.workspace,
        run_id=getattr(args, "run", None),
        run_dir=Path(args.run_dir).resolve() if getattr(args, "run_dir", None) else None,
        after_seq=after_seq,
    )


def cmd_run_advance(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    step_budget = int(getattr(args, "step_budget", None) or 8)
    expected = _parse_expected_revision(args)
    if expected == -1:
        return error("INVALID_REVISION", "revision must be an integer")

    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        if expected is None:
            direct = get_run(
                ctx.workspace,
                run_id=getattr(args, "run", None),
                run_dir=Path(args.run_dir).resolve() if getattr(args, "run_dir", None) else None,
            )
            if not direct.get("ok"):
                return direct
            expected = int(direct.get("revision") or 0)
        import uuid

        return call_host(
            ctx.workspace,
            "run.advance",
            {
                "run_id": getattr(args, "run", None),
                "run_dir": getattr(args, "run_dir", None),
                "flow_id": getattr(args, "flow", None),
                "expected_revision": expected,
                "step_budget": step_budget,
                "idempotency_key": str(uuid.uuid4()),
            },
        )

    return advance_run_durable(
        workspace=ctx.workspace,
        bundle=ctx.bundle,
        run_id=getattr(args, "run", None),
        run_dir=Path(args.run_dir).resolve() if getattr(args, "run_dir", None) else None,
        flow_id=getattr(args, "flow", None),
        expected_revision=expected,
        step_budget=step_budget,
    )


def cmd_run_recover(args: argparse.Namespace) -> dict[str, Any]:
    """Resume a run from durable snapshot (fresh process safe)."""
    setattr(args, "revision", None)
    result = cmd_run_advance(args)
    if result.get("ok"):
        result["recovered"] = True
    return result


def cmd_run_agent_submit(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    expected = _parse_expected_revision(args)
    if expected == -1:
        return error("INVALID_REVISION", "revision must be an integer")

    result_payload: dict[str, Any] | None = None
    if getattr(args, "result_json", None):
        try:
            parsed = json.loads(args.result_json)
        except json.JSONDecodeError as exc:
            return error("INVALID_JSON", f"result-json is not valid JSON: {exc}")
        if not isinstance(parsed, dict):
            return error("INVALID_JSON", "result-json must be a JSON object")
        result_payload = parsed
    elif getattr(args, "result_file", None):
        path = Path(args.result_file).resolve()
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return error("INVALID_JSON", f"Could not read result file: {exc}")
        if not isinstance(parsed, dict):
            return error("INVALID_JSON", "result file must contain a JSON object")
        result_payload = parsed
    else:
        return error("INVALID_REQUEST", "Provide --result-json or --result-file")

    request_id = getattr(args, "request_id", None)
    if not request_id:
        return error("INVALID_REQUEST", "--request-id is required")

    loaded = ctx.load_run(args)
    if isinstance(loaded, dict):
        return loaded
    run_dir, snapshot, visit, flow = loaded
    node = get_node(flow, str(visit["node_id"]))
    denied = _require_capability(node, CAP_RUN_AGENT_SUBMIT)
    if denied:
        return denied
    not_open = _require_opened(visit)
    if not_open:
        return not_open
    wait = snapshot.get("wait")
    if not isinstance(wait, dict) or wait.get("kind") != "agent":
        return error(
            "WAIT_MISMATCH",
            "run agent submit requires an active agent wait on the opened visit",
            wait_kind=wait.get("kind") if isinstance(wait, dict) else None,
        )

    if host_is_running(ctx.workspace) and not getattr(args, "local", False):
        if expected is None:
            direct = get_run(
                ctx.workspace,
                run_id=getattr(args, "run", None),
                run_dir=Path(args.run_dir).resolve() if getattr(args, "run_dir", None) else None,
            )
            if not direct.get("ok"):
                return direct
            expected = int(direct.get("revision") or 0)
        return call_host(
            ctx.workspace,
            "run.agent.submit",
            {
                "run_id": getattr(args, "run", None),
                "run_dir": getattr(args, "run_dir", None),
                "request_id": request_id,
                "result": result_payload,
                "expected_revision": expected,
                "idempotency_key": str(uuid.uuid4()),
            },
        )

    return submit_agent_result_durable(
        workspace=ctx.workspace,
        bundle=ctx.bundle,
        run_id=getattr(args, "run", None),
        run_dir=run_dir,
        request_id=str(request_id),
        result=result_payload,
        expected_revision=expected,
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

    if "clarifying_questions" in patched:
        sync_open_clarifying_questions_count(snapshot)

    persist_err = _persist_run(run_dir, snapshot, args)
    if persist_err:
        return persist_err
    return ok(
        visit_id=visit.get("id"),
        node_id=visit.get("node_id"),
        lifecycle=visit.get("lifecycle"),
        patched_paths=patched,
        rejected_paths=rejected,
        revision=get_revision(snapshot),
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

    persist_err = _persist_run(run_dir, snapshot, args)
    if persist_err:
        return persist_err
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
        revision=get_revision(snapshot),
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
    persist_err = _persist_run(run_dir, snapshot, args)
    if persist_err:
        return persist_err
    return ok(
        receipt_id=sealed.get("receipt_id"),
        path=sealed_uri,
        schema=schema_ref,
        visit_id=visit_id,
        node_id=visit.get("node_id"),
        ledger_seq=event.get("seq"),
        revision=get_revision(snapshot),
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
    if result.get("ok"):
        clear_run_wait(snapshot)
    persist_err = _persist_run(run_dir, snapshot, args)
    if persist_err:
        return persist_err
    engine_response = from_engine_result(result)
    if engine_response.get("ok"):
        engine_response["revision"] = get_revision(snapshot)
    return engine_response


def cmd_visit_intake_complete(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    loaded = ctx.load_run(args)
    if isinstance(loaded, dict):
        return loaded
    run_dir, snapshot, visit, flow = loaded

    node = get_node(flow, str(visit["node_id"]))
    denied = _require_capability(node, CAP_VISIT_INTAKE_COMPLETE)
    if denied:
        return denied
    not_open = _require_opened(visit)
    if not_open:
        return not_open

    work_prompt = getattr(args, "work_prompt", None)
    source_type = str(getattr(args, "source_type", None) or "chat")
    source_ref = getattr(args, "source_ref", None)

    result = run_shape_intake_complete(
        snapshot,
        visit,
        flow,
        workspace=ctx.workspace,
        foundry_bundle=ctx.bundle,
        run_dir=run_dir,
        work_prompt=work_prompt,
        source_type=source_type,
        source_ref=source_ref,
        summary=getattr(args, "summary", None),
    )
    if result.get("ok"):
        clear_run_wait(snapshot)
    persist_err = _persist_run(run_dir, snapshot, args)
    if persist_err:
        return persist_err
    if not result.get("ok"):
        return from_engine_result(result)
    return ok(revision=get_revision(snapshot), **{k: v for k, v in result.items() if k != "ok"})


def cmd_visit_examine_complete(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    loaded = ctx.load_run(args)
    if isinstance(loaded, dict):
        return loaded
    run_dir, snapshot, visit, flow = loaded

    node = get_node(flow, str(visit["node_id"]))
    denied = _require_capability(node, CAP_VISIT_EXAMINE_COMPLETE)
    if denied:
        return denied
    not_open = _require_opened(visit)
    if not_open:
        return not_open

    result = run_shape_examine_complete(
        snapshot,
        visit,
        flow,
        workspace=ctx.workspace,
        foundry_bundle=ctx.bundle,
        run_dir=run_dir,
        summary=getattr(args, "summary", None),
        with_open_questions=bool(getattr(args, "with_open_questions", False)),
    )
    if result.get("ok"):
        clear_run_wait(snapshot)
    persist_err = _persist_run(run_dir, snapshot, args)
    if persist_err:
        return persist_err
    if not result.get("ok"):
        return from_engine_result(result)
    return ok(revision=get_revision(snapshot), **{k: v for k, v in result.items() if k != "ok"})


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
    if result.get("ok"):
        clear_run_wait(snapshot)
    persist_err = _persist_run(run_dir, snapshot, args)
    if persist_err:
        return persist_err
    engine_response = from_engine_result(result)
    if engine_response.get("ok"):
        engine_response["revision"] = get_revision(snapshot)
    return engine_response


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
