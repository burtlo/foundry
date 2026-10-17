"""Parked-run projection for operator status, history, and TUI (run block visibility)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.engine.advance import TERMINAL_RUN_STATUSES
from foundry_cli.engine.operator import EXECUTE_START_NODE_ID
from foundry_cli.engine.run_status_reason import status_reason_payload
from foundry_cli.registry import get_node
from foundry_cli.run_labels import needs_label, node_step_title, run_status_label
from foundry_cli.util import list_or_empty

_PERSON_WAIT_KINDS = frozenset({"operator", "decision", "user_input"})


def _active_visit(snapshot: dict[str, Any]) -> dict[str, Any]:
    active = snapshot.get("active_visit")
    return active if isinstance(active, dict) else {}


def _wait_kind(snapshot: dict[str, Any]) -> str:
    wait = snapshot.get("wait")
    if not isinstance(wait, dict):
        return ""
    return str(wait.get("kind") or "").strip()


def _run_status(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("status") or "running").strip().lower()


def _is_parked(snapshot: dict[str, Any]) -> bool:
    status = _run_status(snapshot)
    wait_kind = _wait_kind(snapshot)

    if wait_kind == "agent":
        return False
    if status == "completed":
        return False
    if status == "running" and wait_kind not in _PERSON_WAIT_KINDS:
        return False

    if wait_kind in _PERSON_WAIT_KINDS:
        return True
    if status in {"halted", "paused", "execution_error", "definition_error"}:
        return True
    return False


def _parse_findings_markdown(text: str) -> list[str]:
    lines = text.splitlines()
    in_findings = False
    findings: list[str] = []
    for line in lines:
        if line.strip() == "## Findings":
            in_findings = True
            continue
        if not in_findings:
            continue
        if line.startswith("## "):
            break
        stripped = line.strip()
        if stripped.startswith("- "):
            findings.append(stripped[2:].strip())
    return findings


def _findings_from_sealed_assessment(run_dir: Path) -> list[str]:
    path = run_dir / "receipts" / "assessment.md"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return _parse_findings_markdown(text)


def _gate_decide_options(flow: dict[str, Any], node_id: str) -> list[str]:
    try:
        node = get_node(flow, node_id)
    except KeyError:
        return ["accept", "reject"]
    produces = node.get("produces") or {}
    options = list_or_empty(produces.get("options"))
    if options:
        return options
    return ["accept", "reject"]


def _parked_heading(snapshot: dict[str, Any], wait_kind: str) -> str:
    if wait_kind in _PERSON_WAIT_KINDS:
        return needs_label(wait_kind)
    return run_status_label(_run_status(snapshot))


def _parked_message(snapshot: dict[str, Any], wait: dict[str, Any] | None) -> str:
    reason = status_reason_payload(snapshot)
    if isinstance(reason, dict):
        message = reason.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    if isinstance(wait, dict):
        summary = wait.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    return ""


def _lawful_commands(
    snapshot: dict[str, Any],
    flow: dict[str, Any],
    *,
    node_id: str,
    wait_kind: str,
) -> list[str]:
    run_id = str(snapshot.get("run_id") or "").strip()
    if not run_id:
        return []

    status = _run_status(snapshot)
    reason = status_reason_payload(snapshot) or {}
    commands: list[str] = []

    if (
        status not in TERMINAL_RUN_STATUSES
        and status != "paused"
        and wait_kind == "operator"
    ):
        commands.append(f"foundry run advance --run {run_id}")

    if reason.get("retry_eligible") is True:
        commands.append(f"foundry retry {run_id}")

    if wait_kind == "user_input":
        commands.append(f"foundry answer {run_id}")

    if wait_kind == "decision" and node_id != EXECUTE_START_NODE_ID:
        for option in _gate_decide_options(flow, node_id):
            commands.append(f"foundry decide {run_id} {option}")

    if wait_kind == "decision" and node_id == EXECUTE_START_NODE_ID:
        commands.append(f"foundry start {run_id}")

    return commands


def build_parked_run_projection(
    snapshot: dict[str, Any],
    flow: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any] | None:
    """Return parked-run fields for status/history/TUI, or ``None`` when not parked."""
    if not _is_parked(snapshot):
        return None

    visit = _active_visit(snapshot)
    node_id = str(visit.get("node_id") or "").strip()
    wait = snapshot.get("wait") if isinstance(snapshot.get("wait"), dict) else None
    wait_kind = _wait_kind(snapshot)

    record: dict[str, Any] = {
        "heading": _parked_heading(snapshot, wait_kind),
        "step_title": node_step_title(node_id or None, flow),
        "node_id": node_id,
        "message": _parked_message(snapshot, wait),
        "findings": _findings_from_sealed_assessment(run_dir),
        "commands": _lawful_commands(snapshot, flow, node_id=node_id, wait_kind=wait_kind),
    }

    reason = status_reason_payload(snapshot)
    if isinstance(reason, dict):
        code = reason.get("code")
        if isinstance(code, str) and code.strip():
            record["reason_code"] = code.strip()

    return record
