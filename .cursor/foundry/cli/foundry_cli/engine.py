"""Workflow engine: hooks, checks, admission, and transition."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from foundry_cli.app_manifest import validate_manifest
from foundry_cli.ledger import append_event, count_events, has_artifact_linked, last_event
from foundry_cli.paths import resolve_run_uri, resolve_workspace_uri, substitute_visit_id
from foundry_cli.registry import get_node, normalize_receipts
from foundry_cli.validate import validate_payload

# Snapshot run_id is a human slug (e.g. porcelain-0007). Receipt schemas require UUID
# run_id — we store run_uuid at create time and use it when sealing receipts.
RUN_UUID_KEY = "run_uuid"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_uuid(snapshot: dict[str, Any]) -> str:
    value = snapshot.get(RUN_UUID_KEY)
    if isinstance(value, str) and value:
        return value
    return str(snapshot.get("run_id") or "")


def next_visit_id(snapshot: dict[str, Any]) -> str:
    visits = snapshot.get("visits")
    max_num = 0
    if isinstance(visits, list):
        for visit in visits:
            if isinstance(visit, dict):
                match = re.fullmatch(r"v-(\d+)", str(visit.get("id", "")))
                if match:
                    max_num = max(max_num, int(match.group(1)))
    active = snapshot.get("active_visit")
    if isinstance(active, dict):
        match = re.fullmatch(r"v-(\d+)", str(active.get("id", "")))
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"v-{max_num + 1:03d}"


def generate_run_slug(workspace: Path, manifest_id: str | None) -> str:
    runs_dir = workspace / ".foundry" / "runs"
    prefix = manifest_id or "run"
    max_num = 0
    if runs_dir.is_dir():
        pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
        for child in runs_dir.iterdir():
            if child.is_dir():
                match = pattern.match(child.name)
                if match:
                    max_num = max(max_num, int(match.group(1)))
    return f"{prefix}-{max_num + 1:04d}"


def active_visit(snapshot: dict[str, Any]) -> dict[str, Any]:
    visit = snapshot.get("active_visit")
    if not isinstance(visit, dict):
        raise ValueError("snapshot has no active_visit")
    return visit


def ensure_visits_list(snapshot: dict[str, Any], visit: dict[str, Any]) -> None:
    visits = snapshot.setdefault("visits", [])
    if not isinstance(visits, list):
        visits = []
        snapshot["visits"] = visits
    visit_id = visit.get("id")
    for existing in visits:
        if isinstance(existing, dict) and existing.get("id") == visit_id:
            return
    visits.append(deepcopy(visit))


def update_active_visit(snapshot: dict[str, Any], visit: dict[str, Any]) -> None:
    snapshot["active_visit"] = visit
    visits = snapshot.setdefault("visits", [])
    if not isinstance(visits, list):
        visits = []
        snapshot["visits"] = visits
    for index, existing in enumerate(visits):
        if isinstance(existing, dict) and existing.get("id") == visit.get("id"):
            visits[index] = visit
            return
    visits.append(visit)


def flow_checks(flow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = flow.get("checks") or {}
    if isinstance(checks, dict):
        return {str(key): value for key, value in checks.items() if isinstance(value, dict)}
    return {}


def flow_connections(flow: dict[str, Any]) -> list[dict[str, Any]]:
    connections = flow.get("connections") or []
    return [item for item in connections if isinstance(item, dict)]


def _snapshot_state_value(snapshot: dict[str, Any], key: str) -> Any:
    state = snapshot.get("state")
    if not isinstance(state, dict):
        return None
    return state.get(key)


def _visit_sealed_check(snapshot: dict[str, Any], node_id: str, expr: str) -> bool:
    event = last_event(snapshot, "visit.sealed", node_id=node_id)
    if event is None:
        return "!= null" not in expr
    payload = event.get("payload") or {}
    if "outcome == 'completed'" in expr:
        return payload.get("outcome") == "completed"
    return event is not None


def evaluate_when_expression(snapshot: dict[str, Any], visit: dict[str, Any], expr: str) -> bool:
    """Minimal evaluator for catalog when expressions used in shape vertical slice."""
    expr = expr.strip()
    visit_id = str(visit.get("id", ""))

    if "history.count('receipt.linked'" in expr and "intake-receipt" in expr:
        return (
            count_events(
                snapshot,
                "receipt.linked",
                visit_id=visit_id,
                schema="registry:schemas/intake-receipt.schema.json",
            )
            >= 1
        )
    if "history.count('receipt.linked'" in expr and "agent-receipt" in expr:
        return (
            count_events(
                snapshot,
                "receipt.linked",
                visit_id=visit_id,
                schema="registry:schemas/agent-receipt.schema.json",
            )
            >= 1
        )
    if "state.open_clarifying_questions_count == 0" in expr:
        return _snapshot_state_value(snapshot, "open_clarifying_questions_count") == 0
    if "state.open_clarifying_questions_count != 0" in expr:
        count = _snapshot_state_value(snapshot, "open_clarifying_questions_count")
        return count is not None and count != 0
    for node_id in ("shape.intake", "shape.examine"):
        marker = f"history.last('visit.sealed', node_id='{node_id}')"
        if marker in expr:
            return _visit_sealed_check(snapshot, node_id, expr)
    return True


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
        return {"result": "pass" if result["passed"] else "fail", "detail": result}
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
        return {"passed": True, "actions": []}

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
            return {"passed": False, "action": action, "reason": reason, "check_id": check_id}

        append_event(
            snapshot,
            event_type="policy.applied",
            visit_id=visit_id,
            node_id=node_id,
            payload={"check_id": check_id, "action": "continue"},
        )

    return {"passed": True, "actions": []}


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
        return {"passed": False, "missing": missing}
    return {"passed": True, "missing": []}


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
    if not completeness["passed"]:
        append_event(
            snapshot,
            event_type="check.recorded",
            visit_id=visit_id,
            node_id=node_id,
            payload={"hook": "on_close", "check_id": "(artifact completeness)", "result": "fail", "missing": completeness["missing"]},
        )
        append_event(
            snapshot,
            event_type="policy.applied",
            visit_id=visit_id,
            node_id=node_id,
            payload={"check_id": "on_close", "action": "block"},
        )
        return {"passed": False, "reason": f"Missing artifacts: {', '.join(completeness['missing'])}"}

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
    return {"passed": True}


def admit_visit(
    snapshot: dict[str, Any],
    *,
    node_id: str,
    flow: dict[str, Any],
    source: str,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> dict[str, Any]:
    node = get_node(flow, node_id)
    visit_id = next_visit_id(snapshot)
    visit = {
        "id": visit_id,
        "node_id": node_id,
        "kind": str(node.get("kind", "step")),
        "lifecycle": "admitted",
        "outcome": None,
        "decision": None,
    }
    update_active_visit(snapshot, visit)
    append_event(
        snapshot,
        event_type="visit.admitted",
        visit_id=visit_id,
        node_id=node_id,
        payload={"source": source},
    )

    visit["lifecycle"] = "examined"
    update_active_visit(snapshot, visit)
    append_event(
        snapshot,
        event_type="lifecycle.changed",
        visit_id=visit_id,
        node_id=node_id,
        payload={"from": "admitted", "to": "examined"},
    )

    examine_result = run_hook(
        snapshot,
        visit,
        flow,
        "on_examine",
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    if not examine_result["passed"]:
        action = examine_result.get("action", "halt")
        if action == "halt":
            snapshot["status"] = "halted"
            append_event(
                snapshot,
                event_type="run.status_changed",
                payload={"prior_status": "running", "new_status": "halted", "reason": examine_result.get("reason")},
            )
        return visit

    open_result = run_hook(
        snapshot,
        visit,
        flow,
        "on_open",
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    if not open_result["passed"]:
        action = open_result.get("action", "halt")
        if action == "halt":
            prior = str(snapshot.get("status", "running"))
            snapshot["status"] = "halted"
            append_event(
                snapshot,
                event_type="run.status_changed",
                payload={"prior_status": prior, "new_status": "halted", "reason": open_result.get("reason")},
            )
        return visit

    visit["lifecycle"] = "opened"
    update_active_visit(snapshot, visit)
    append_event(
        snapshot,
        event_type="lifecycle.changed",
        visit_id=visit_id,
        node_id=node_id,
        payload={"from": "examined", "to": "opened"},
    )
    return visit


def select_connection(
    snapshot: dict[str, Any],
    from_node_id: str,
    flow: dict[str, Any],
    outcome: str = "completed",
) -> dict[str, Any] | None:
    visit = active_visit(snapshot)
    unconditional: list[dict[str, Any]] = []
    conditional: list[dict[str, Any]] = []
    for connection in flow_connections(flow):
        if connection.get("from") != from_node_id:
            continue
        on_block = connection.get("on") or {}
        outcomes = on_block.get("outcomes") or []
        if outcome not in outcomes:
            continue
        when_expr = connection.get("when")
        if when_expr:
            if evaluate_when_expression(snapshot, visit, str(when_expr)):
                conditional.append(connection)
        else:
            unconditional.append(connection)
    if conditional:
        return conditional[0]
    if unconditional:
        return unconditional[0]
    return None


def transition_visit(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    summary: str | None = None,
) -> dict[str, Any]:
    if str(visit.get("lifecycle")) != "opened":
        return {"ok": False, "code": "VISIT_NOT_OPENED", "message": f"Visit lifecycle is {visit.get('lifecycle')!r}, expected 'opened'"}

    if str(snapshot.get("status")) == "halted":
        return {"ok": False, "code": "RUN_HALTED", "message": "Run is halted"}

    visit_id = str(visit["id"])
    node_id = str(visit["node_id"])
    prior_lifecycle = str(visit["lifecycle"])

    close_result = run_on_close(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    if not close_result["passed"]:
        return {
            "ok": False,
            "code": "ARTIFACT_INCOMPLETE",
            "message": close_result.get("reason", "on_close checks failed"),
        }

    visit["lifecycle"] = "closed"
    update_active_visit(snapshot, visit)
    append_event(
        snapshot,
        event_type="lifecycle.changed",
        visit_id=visit_id,
        node_id=node_id,
        payload={"from": "opened", "to": "closed"},
    )

    seal_result = run_hook(
        snapshot,
        visit,
        flow,
        "on_seal",
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )
    if not seal_result["passed"]:
        action = seal_result.get("action", "reopen")
        if action == "reopen":
            visit["lifecycle"] = "opened"
            update_active_visit(snapshot, visit)
            append_event(
                snapshot,
                event_type="lifecycle.changed",
                visit_id=visit_id,
                node_id=node_id,
                payload={"from": "closed", "to": "opened"},
            )
            return {
                "ok": False,
                "code": "CHECK_FAILED",
                "message": seal_result.get("reason", "on_seal check failed"),
                "reopened": True,
                "visit_id": visit_id,
                "node_id": node_id,
                "prior_lifecycle": prior_lifecycle,
                "lifecycle": "opened",
                "policy": {"check": seal_result.get("check_id"), "action": "reopen"},
            }
        return {"ok": False, "code": "CHECK_FAILED", "message": seal_result.get("reason", "on_seal failed")}

    visit["lifecycle"] = "sealed"
    visit["outcome"] = "completed"
    update_active_visit(snapshot, visit)
    append_event(
        snapshot,
        event_type="lifecycle.changed",
        visit_id=visit_id,
        node_id=node_id,
        payload={"from": "closed", "to": "sealed"},
    )
    append_event(
        snapshot,
        event_type="visit.sealed",
        visit_id=visit_id,
        node_id=node_id,
        payload={"outcome": "completed", "summary": summary},
    )

    connection = select_connection(snapshot, node_id, flow)
    if connection is None:
        return {
            "ok": True,
            "visit_id": visit_id,
            "node_id": node_id,
            "prior_lifecycle": prior_lifecycle,
            "lifecycle": "sealed",
            "outcome": "completed",
            "connection": None,
        }

    connection_id = str(connection.get("id", ""))
    to_node_id = str(connection.get("to", ""))
    append_event(
        snapshot,
        event_type="connection.taken",
        visit_id=visit_id,
        node_id=node_id,
        payload={"connection_id": connection_id, "to_node_id": to_node_id},
    )

    next_visit = admit_visit(
        snapshot,
        node_id=to_node_id,
        flow=flow,
        source=connection_id,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
    )

    return {
        "ok": True,
        "visit_id": visit_id,
        "node_id": node_id,
        "prior_lifecycle": prior_lifecycle,
        "lifecycle": "sealed",
        "outcome": "completed",
        "connection": {"connection_id": connection_id, "to_node_id": to_node_id},
        "next_visit_id": next_visit.get("id"),
        "next_node_id": to_node_id,
        "next_lifecycle": next_visit.get("lifecycle"),
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


def seal_receipt_path(schema_ref: str, visit_id: str) -> str:
    if "intake-receipt" in schema_ref:
        return f"run:receipts/{visit_id}/intake-receipt.json"
    if "agent-receipt" in schema_ref:
        return f"run:receipts/{visit_id}/agent-receipt.json"
    return f"run:receipts/{visit_id}/receipt.json"


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
    if "intake-receipt" in schema_ref:
        filled["step_id"] = filled.get("step_id") or str(visit["node_id"])
    if "agent-receipt" in schema_ref:
        provenance = filled.get("provenance") if isinstance(filled.get("provenance"), dict) else {}
        provenance.setdefault("source", "cli_seal")
        provenance.setdefault("cli_command", "receipt seal")
        provenance.setdefault("run_id", run_uuid(snapshot))
        provenance.setdefault("step_id", str(visit["node_id"]))
        filled["provenance"] = provenance
        filled.setdefault("recommended_next_state", str(visit["node_id"]))
    return filled


def allowed_state_paths(node: dict[str, Any], node_id: str) -> set[str]:
    allow = node.get("allow") or {}
    state_paths = allow.get("state") or []
    paths = {str(item) for item in state_paths}
    paths.add(f"state.nodes.{node_id}.*")
    return paths


def patch_allowed(snapshot: dict[str, Any], node: dict[str, Any], node_id: str, patch: dict[str, Any]) -> tuple[list[str], list[str]]:
    allow = node.get("allow") or {}
    explicit = {str(item) for item in (allow.get("state") or [])}
    node_scope_prefix = f"nodes.{node_id}."
    state = snapshot.setdefault("state", {})
    if not isinstance(state, dict):
        state = {}
        snapshot["state"] = state
    patched: list[str] = []
    rejected: list[str] = []
    for key, value in patch.items():
        if key in explicit or str(key).startswith(node_scope_prefix):
            state[key] = value
            patched.append(key)
        else:
            rejected.append(key)
    return patched, rejected
