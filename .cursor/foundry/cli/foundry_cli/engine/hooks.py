"""Lifecycle hook execution and on-close checks."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from foundry_cli.app_manifest import validate_manifest
from foundry_cli.engine.evidence import (
    AGENT_RECEIPT_SCHEMA,
    load_linked_receipt,
    sealed_step_visit_id,
)
from foundry_cli.engine.loop_limits import evaluate_limit_flow_check
from foundry_cli.engine.routing import WhenExpressionError, evaluate_when_expression, flow_checks
from foundry_cli.ledger import append_event, has_artifact_linked, last_event, ledger_events
from foundry_cli.paths import resolve_run_uri
from foundry_cli.registry import get_node


def _snapshot_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    state = snapshot.get("state")
    return state if isinstance(state, dict) else {}


def _load_agent_receipt_for_visit(
    snapshot: dict[str, Any],
    visit_id: str,
    run_dir: Path,
) -> dict[str, Any] | None:
    return load_linked_receipt(snapshot, visit_id, AGENT_RECEIPT_SCHEMA, run_dir)


def _latest_sealed_visit_id(snapshot: dict[str, Any], node_id: str) -> str | None:
    return sealed_step_visit_id(snapshot, node_id)


def _check_validate_git_clean_execute(workspace: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return {"result": "fail", "detail": {"reason": "git_unavailable", "error": str(exc)}}
    if completed.returncode != 0:
        return {
            "result": "fail",
            "detail": {"reason": "git_status_failed", "exit_code": completed.returncode},
        }
    dirty = bool(completed.stdout.strip())
    if dirty:
        return {"result": "fail", "detail": {"reason": "dirty_worktree"}}
    return {"result": "pass", "detail": {}}


def _check_validate_verify_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    state = _snapshot_state(snapshot)
    required = ("feature_branch", "default_branch", "final_commit_sha", "execution_graph_id")
    missing = [key for key in required if not state.get(key)]
    if missing:
        return {"result": "fail", "detail": {"reason": "missing_state", "missing": missing}}
    return {"result": "pass", "detail": {}}


def _check_ensure_execution_graph_reference(snapshot: dict[str, Any]) -> dict[str, Any]:
    state = _snapshot_state(snapshot)
    if state.get("execution_graph_id"):
        return {"result": "pass", "detail": {}}
    return {"result": "fail", "detail": {"reason": "execution_graph_id_missing"}}


def _check_validate_build_exit(
    snapshot: dict[str, Any],
    run_dir: Path,
    *,
    visit_id: str | None = None,
) -> dict[str, Any]:
    build_visit_id = visit_id or _latest_sealed_visit_id(snapshot, "execute.build")
    if not build_visit_id:
        return {"result": "fail", "detail": {"reason": "execute.build_not_sealed"}}
    receipt = _load_agent_receipt_for_visit(snapshot, build_visit_id, run_dir)
    if receipt is None:
        return {"result": "fail", "detail": {"reason": "build_receipt_missing"}}
    if receipt.get("_missing_file"):
        return {"result": "fail", "detail": {"reason": "build_receipt_file_missing", "path": receipt["_missing_file"]}}

    commands = receipt.get("commands")
    if isinstance(commands, list) and commands:
        failed = [item for item in commands if isinstance(item, dict) and item.get("exit_code", 1) != 0]
        if failed:
            return {"result": "fail", "detail": {"reason": "build_command_failed", "failed": failed}}
        return {"result": "pass", "detail": {"commands_checked": len(commands)}}

    status = receipt.get("status")
    if status == "completed":
        return {"result": "pass", "detail": {"status": status}}
    return {"result": "fail", "detail": {"reason": "build_receipt_not_passing", "status": status}}


def run_command_check(
    check_id: str,
    check_def: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    snapshot: dict[str, Any] | None = None,
    run_dir: Path | None = None,
    visit_id: str | None = None,
) -> dict[str, Any]:
    command = check_def.get("command")
    if command == "validate_manifest":
        result = validate_manifest(workspace, foundry_bundle)
        return {"result": "pass" if result["ok"] else "fail", "detail": result}
    if command == "validate_git_clean_execute":
        return _check_validate_git_clean_execute(workspace)
    if command == "validate_verify_context":
        if snapshot is None:
            return {"result": "fail", "detail": {"reason": "snapshot_required"}}
        return _check_validate_verify_context(snapshot)
    if command == "ensure_execution_graph_reference":
        if snapshot is None:
            return {"result": "fail", "detail": {"reason": "snapshot_required"}}
        return _check_ensure_execution_graph_reference(snapshot)
    if command == "validate_build_exit":
        if snapshot is None or run_dir is None:
            return {"result": "fail", "detail": {"reason": "snapshot_and_run_dir_required"}}
        return _check_validate_build_exit(snapshot, run_dir, visit_id=visit_id)
    return {
        "result": "fail",
        "detail": {"reason": "unknown_command", "command": command, "check_id": check_id},
    }


def run_hook(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    hook_name: str,
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> dict[str, Any]:
    node_id = str(visit["node_id"])
    node = get_node(flow, node_id)
    lifecycle = node.get("lifecycle") or {}
    hook_checks = lifecycle.get(hook_name) or []
    if not isinstance(hook_checks, list) or not hook_checks:
        return {"ok": True, "actions": []}

    catalog = flow_checks(flow)
    visit_id = str(visit["id"])

    for hook_entry in hook_checks:
        if not isinstance(hook_entry, dict):
            continue
        check_id = str(hook_entry.get("check", ""))
        check_def = catalog.get(check_id)
        if not check_def:
            result = "fail"
            detail: dict[str, Any] = {"reason": "unknown_check_id", "check_id": check_id}
        elif "when" in check_def:
            try:
                limit_pass = evaluate_limit_flow_check(snapshot, check_id)
                if limit_pass is not None:
                    passed = limit_pass
                else:
                    passed = evaluate_when_expression(snapshot, visit, str(check_def["when"]))
                result = "pass" if passed else "fail"
                detail = {}
            except WhenExpressionError as exc:
                result = "fail"
                detail = {"reason": "when_expression_error", "expr": exc.expr, "message": str(exc)}
        elif "command" in check_def:
            probe = run_command_check(
                check_id,
                check_def,
                workspace=workspace,
                foundry_bundle=foundry_bundle,
                snapshot=snapshot,
                run_dir=run_dir,
                visit_id=visit_id,
            )
            result = probe["result"]
            detail = probe.get("detail") or {}
        else:
            result = "fail"
            detail = {"reason": "no_evaluator", "check_id": check_id}

        append_event(
            snapshot,
            event_type="check.recorded",
            visit_id=visit_id,
            node_id=node_id,
            payload={"hook": hook_name, "check_id": check_id, "result": result, **({"detail": detail} if detail else {})},
        )

        on_fail = hook_entry.get("on_fail") or {}
        if result == "fail":
            action = on_fail.get("action", "halt")
            reason = on_fail.get("reason", f"Check {check_id} failed")
            append_event(
                snapshot,
                event_type="policy.applied",
                visit_id=visit_id,
                node_id=node_id,
                payload={"check_id": check_id, "action": action},
            )
            return {
                "ok": False,
                "code": "CHECK_FAILED",
                "message": reason,
                "action": action,
                "check_id": check_id,
            }

        append_event(
            snapshot,
            event_type="policy.applied",
            visit_id=visit_id,
            node_id=node_id,
            payload={"check_id": check_id, "action": "continue"},
        )

    return {"ok": True, "actions": []}


def artifact_completeness(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
) -> dict[str, Any]:
    node = get_node(flow, str(visit["node_id"]))
    produces = (node.get("produces") or {}).get("artifacts") or []
    visit_id = str(visit["id"])
    missing: list[str] = []
    for artifact in produces:
        if not isinstance(artifact, dict):
            continue
        artifact_id = str(artifact.get("id", ""))
        if not has_artifact_linked(snapshot, visit_id=visit_id, artifact_id=artifact_id):
            missing.append(artifact_id)
    if missing:
        return {"ok": False, "code": "ARTIFACT_INCOMPLETE", "message": f"Missing artifacts: {', '.join(missing)}", "missing": missing}
    return {"ok": True, "missing": []}


def run_on_close(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> dict[str, Any]:
    completeness = artifact_completeness(snapshot, visit, flow)
    visit_id = str(visit["id"])
    node_id = str(visit["node_id"])
    if not completeness["ok"]:
        append_event(
            snapshot,
            event_type="check.recorded",
            visit_id=visit_id,
            node_id=node_id,
            payload={
                "hook": "on_close",
                "check_id": "(artifact completeness)",
                "result": "fail",
                "missing": completeness.get("missing", []),
            },
        )
        append_event(
            snapshot,
            event_type="policy.applied",
            visit_id=visit_id,
            node_id=node_id,
            payload={"check_id": "on_close", "action": "block"},
        )
        return {
            "ok": False,
            "code": completeness.get("code", "ARTIFACT_INCOMPLETE"),
            "message": completeness.get("message", "on_close checks failed"),
        }

    append_event(
        snapshot,
        event_type="check.recorded",
        visit_id=visit_id,
        node_id=node_id,
        payload={"hook": "on_close", "check_id": "(step checks)", "result": "pass"},
    )
    append_event(
        snapshot,
        event_type="policy.applied",
        visit_id=visit_id,
        node_id=node_id,
        payload={"check_id": "on_close", "action": "continue"},
    )
    return {"ok": True}
