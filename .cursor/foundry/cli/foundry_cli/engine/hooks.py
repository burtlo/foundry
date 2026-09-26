"""Lifecycle hook execution and on-close checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.app_manifest import validate_manifest
from foundry_cli.engine.routing import evaluate_when_expression, flow_checks
from foundry_cli.ledger import append_event, has_artifact_linked
from foundry_cli.registry import get_node


def run_command_check(
    check_id: str,
    check_def: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
) -> dict[str, Any]:
    command = check_def.get("command")
    if command == "validate_manifest":
        result = validate_manifest(workspace, foundry_bundle)
        return {"result": "pass" if result["ok"] else "fail", "detail": result}
    return {"result": "pass", "detail": {}}


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
        check_def = catalog.get(check_id, {})
        if "when" in check_def:
            passed = evaluate_when_expression(snapshot, visit, str(check_def["when"]))
            result = "pass" if passed else "fail"
            detail: dict[str, Any] = {}
        elif "command" in check_def:
            probe = run_command_check(check_id, check_def, workspace=workspace, foundry_bundle=foundry_bundle)
            result = probe["result"]
            detail = probe.get("detail") or {}
        else:
            result = "pass"
            detail = {}

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
