"""Assemble steward context packets (shared by CLI and job host)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from foundry_cli.context import assemble_context
from foundry_cli.registry import get_node, load_registry
from foundry_cli.errors import error, ok
from foundry_cli.render import render_context_markdown
from foundry_cli.run_store import (
    RunStoreError,
    get_revision,
    load_snapshot,
    resolve_run_dir,
    select_visit,
)
from foundry_cli.validate import validate_payload

ContextFormat = Literal["json", "markdown"]


def _read_context_companion_files(
    context: dict[str, Any],
) -> dict[str, Any] | tuple[str, str]:
    instructions_path = str(context.get("instructions_path") or "")
    instructions_text = ""
    if instructions_path:
        try:
            instructions_text = Path(instructions_path).read_text(encoding="utf-8")
        except OSError as exc:
            return error(
                "INSTRUCTIONS_READ_FAILED",
                f"Could not read instructions at {instructions_path!r}: {exc}",
            )
    operations_path = str(context.get("operations_path") or "")
    operations_text = ""
    if operations_path:
        try:
            operations_text = Path(operations_path).read_text(encoding="utf-8")
        except OSError as exc:
            return error(
                "OPERATIONS_READ_FAILED",
                f"Could not read operations at {operations_path!r}: {exc}",
            )
    return instructions_text, operations_text


def build_run_context(
    workspace: Path,
    bundle: Path,
    *,
    run_id: str | None = None,
    run_dir: Path | None = None,
    visit_id: str | None = None,
    flow_id: str | None = None,
    output_format: ContextFormat = "json",
) -> dict[str, Any]:
    try:
        resolved = resolve_run_dir(run_id=run_id, run_dir=run_dir, workspace=workspace)
        snapshot = load_snapshot(resolved)
        visit = select_visit(snapshot, visit_id)
        resolved_flow_id = flow_id or str(snapshot.get("flow_id") or "implementation")
        _, flow = load_registry(bundle, flow_id=resolved_flow_id)
    except RunStoreError as exc:
        return error(exc.code, exc.message)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        return error("INVALID_REQUEST", str(exc))

    try:
        get_node(flow, str(visit["node_id"]))
    except KeyError as exc:
        return error("NODE_NOT_FOUND", f"Node not found in flow registry: {exc.args[0]}")

    try:
        context = assemble_context(
            snapshot=snapshot,
            visit=visit,
            flow=flow,
            foundry_bundle=bundle,
            run_dir=resolved,
            workspace=workspace,
        )
    except ValueError as exc:
        return error("INVALID_NODE", str(exc))

    schema_errors = validate_payload(context, "context-packet.schema.json", bundle)
    if schema_errors:
        return error("SCHEMA_VALIDATION_FAILED", "; ".join(schema_errors))

    if output_format == "json":
        return ok(
            run_id=snapshot.get("run_id"),
            revision=get_revision(snapshot),
            context=context,
        )

    companion = _read_context_companion_files(context)
    if isinstance(companion, dict):
        return companion
    instructions_text, operations_text = companion
    markdown = render_context_markdown(context, instructions_text, operations_text=operations_text)
    return ok(
        run_id=snapshot.get("run_id"),
        revision=get_revision(snapshot),
        context=context,
        markdown=markdown,
    )
