"""Task-bound visit completion via task YAML advance metadata and ActionRegistry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.engine.actions import ActionExecutionContext, default_action_registry
from foundry_cli.engine.agent.tasks import load_task_definition

_DEFAULT_WAIT_SUMMARY = "Task judgment required ({task_id})"


def task_advance_metadata(task_id: str, foundry_bundle: Path) -> dict[str, str]:
    """Read ``advance`` block from task YAML."""
    try:
        task = load_task_definition(task_id, foundry_bundle)
    except (KeyError, ValueError):
        return {
            "complete_action": "",
            "complete_reason": task_id.replace(".", "_") + "_complete",
            "wait_summary": _DEFAULT_WAIT_SUMMARY.format(task_id=task_id),
        }
    advance = task.get("advance")
    block = advance if isinstance(advance, dict) else {}
    complete_action = str(block.get("complete_action") or "").strip()
    complete_reason = str(block.get("complete_reason") or "").strip()
    wait_summary = str(block.get("wait_summary") or "").strip()
    if not complete_reason:
        complete_reason = task_id.replace(".", "_") + "_complete"
    if not wait_summary:
        wait_summary = _DEFAULT_WAIT_SUMMARY.format(task_id=task_id)
    return {
        "complete_action": complete_action,
        "complete_reason": complete_reason,
        "wait_summary": wait_summary,
    }


def execute_task_bound_complete(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    task_id: str,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> dict[str, Any]:
    """Run judgment step complete action from task YAML ``advance.complete_action``."""
    meta = task_advance_metadata(task_id, foundry_bundle)
    action = meta["complete_action"]
    if not action:
        return {
            "ok": False,
            "code": "TASK_ADVANCE_MISSING_ACTION",
            "message": f"task {task_id}: advance.complete_action is required",
        }
    registry = default_action_registry()
    if not registry.has(action):
        return {
            "ok": False,
            "code": "TASK_ADVANCE_UNKNOWN_ACTION",
            "message": f"task {task_id}: unknown complete_action {action!r}",
        }
    ctx = ActionExecutionContext(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    try:
        return registry.execute(action, ctx, {})
    except KeyError:
        return {
            "ok": False,
            "code": "TASK_ADVANCE_UNKNOWN_ACTION",
            "message": f"task {task_id}: unknown complete_action {action!r}",
        }
