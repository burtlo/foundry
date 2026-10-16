"""Host/CLI service for operator history projection."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from foundry_cli.errors import error, ok
from foundry_cli.operator_history import project_operator_history
from foundry_cli.registry import load_registry
from foundry_cli.run_store import RunStoreError, get_revision, load_snapshot, resolve_run_dir

OperatorHistoryFormat = Literal["json", "markdown"]


def build_operator_history(
    workspace: Path,
    bundle: Path,
    *,
    run_id: str | None = None,
    run_dir: Path | None = None,
    output_format: OperatorHistoryFormat = "json",
) -> dict[str, Any]:
    try:
        resolved = resolve_run_dir(run_id=run_id, run_dir=run_dir, workspace=workspace)
        snapshot = load_snapshot(resolved)
        flow_id = str(snapshot.get("flow_id") or "implementation")
        _, flow = load_registry(bundle, flow_id=flow_id)
    except RunStoreError as exc:
        return error(exc.code, exc.message)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        return error("INVALID_REQUEST", str(exc))

    projection = project_operator_history(snapshot, flow, run_dir=resolved)
    revision = get_revision(snapshot)
    run_key = snapshot.get("run_id")

    if output_format == "markdown":
        return ok(
            run_id=run_key,
            revision=revision,
            markdown=projection.get("markdown") or "",
            sections=projection.get("sections") or [],
        )

    return ok(
        run_id=run_key,
        revision=revision,
        sections=projection.get("sections") or [],
        markdown=projection.get("markdown") or "",
    )
