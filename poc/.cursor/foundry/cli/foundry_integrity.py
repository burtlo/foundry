"""Run integrity checks for Foundry durable truth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import foundry_observability as obs
import foundry_app


class IntegrityError(Exception):
    def __init__(self, error_code: str, message: str, *, issues: list[str] | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.issues = issues or []


def run_integrity_check(
    state_path: Path,
    *,
    events: list[dict[str, Any]] | None = None,
    transcript_findings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    run_dir = state_path.parent
    events_path = run_dir / "events.jsonl"
    loaded_events = events if events is not None else obs.load_events(events_path)
    issues: list[str] = []

    try:
        foundry_app.assert_run_manifest_current(state, run_dir)
    except foundry_app.AppManifestError as exc:
        issues.append(f"{exc.error_code}: {exc.message}")

    # Sealed ticket consistency
    ticket_path = run_dir / "ticket.json"
    if state.get("ticket_sealed") and not ticket_path.is_file():
        issues.append("ticket_sealed=true but ticket.json missing")
    if ticket_path.is_file():
        try:
            ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
            if not isinstance(ticket, dict) or ticket.get("id") != state.get("issue_key"):
                issues.append("ticket.json id does not match state.issue_key")
        except json.JSONDecodeError:
            issues.append("ticket.json is not valid JSON")

    # Receipts must match meta when launch_id known
    receipts_dir = run_dir / "receipts"
    staging_dir = run_dir / "staging"
    if staging_dir.is_dir():
        for meta_path in staging_dir.glob("*.meta.json"):
            launch_id = meta_path.name[: -len(".meta.json")]
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                issues.append(f"invalid meta JSON: {meta_path.name}")
                continue
            receipt_id = meta.get("receipt_id")
            if not isinstance(receipt_id, str):
                continue
            durable = receipts_dir / f"{receipt_id}.json"
            if not durable.is_file():
                # Incomplete launch is OK if still open
                opens = state.get("open_subagent_launches") or []
                still_open = any(
                    isinstance(item, dict) and item.get("launch_id") == launch_id for item in opens
                )
                if not still_open:
                    # completed launches should have durable receipt
                    completed = any(
                        e.get("event_type") in ("subagent_completed", "subagent_failed")
                        and isinstance(e.get("payload"), dict)
                        and e["payload"].get("launch_id") == launch_id
                        for e in loaded_events
                    )
                    if completed:
                        issues.append(f"completed launch {launch_id} missing durable receipt {receipt_id}")
                continue
            try:
                receipt = json.loads(durable.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                issues.append(f"invalid receipt JSON: {receipt_id}")
                continue
            if receipt.get("receipt_id") != meta.get("receipt_id"):
                issues.append(f"receipt {receipt_id} receipt_id != launch meta")
            if receipt.get("run_id") != state.get("run_id"):
                issues.append(f"receipt {receipt_id} run_id mismatch")
            agent = receipt.get("agent") if isinstance(receipt.get("agent"), dict) else {}
            meta_agent = meta.get("agent") if isinstance(meta.get("agent"), dict) else {}
            if agent.get("name") != meta_agent.get("name"):
                issues.append(f"receipt {receipt_id} agent name != launch meta")

    # Transcript integrity findings
    if transcript_findings:
        for finding in transcript_findings.get("findings") or []:
            rule_id = finding.get("rule_id")
            if rule_id in (
                "HAND_WRITE_RECEIPT",
                "RECEIPT_BACKFILL",
                "PARENT_APP_EDIT",
                "RAW_DOTNET_ORCHESTRATOR",
                "STEWARD_WRITE_STAGING",
            ):
                issues.append(f"transcript:{rule_id}")

    # Auto grill with clarifying questions (event-level)
    clarifying = int(state.get("clarifying_questions_count") or 0)
    if clarifying > 0:
        for event in loaded_events:
            if event.get("event_type") != "gate_resolved":
                continue
            if event.get("step_id") != "intake.grill":
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            if payload.get("source") == "auto" or event.get("actor") == "engine":
                # engine auto resolve while clarifying questions remain
                if payload.get("decision") == "approve" and payload.get("source") == "auto":
                    issues.append("auto_grill_with_clarifying_questions")

    # Session stop without handoff: worker/hard stop then more cli without handoff_written
    stop_hints = ("stop_after_worker", "stop_after_hard_gate", "stop_after_build_verify")
    # Soft check: if last subagent_completed exists and no later handoff_written before another transition
    last_complete_idx = None
    last_handoff_idx = None
    for idx, event in enumerate(loaded_events):
        if event.get("event_type") in ("subagent_completed", "subagent_failed"):
            last_complete_idx = idx
        if event.get("event_type") == "handoff_written":
            last_handoff_idx = idx
    if last_complete_idx is not None:
        later_transition = any(
            e.get("event_type") == "state_transition" for e in loaded_events[last_complete_idx + 1 :]
        )
        # After worker complete, next state_transition is OK (complete of the step);
        # further transitions without handoff are flagged when multiple transitions follow.
        transitions_after = [
            e for e in loaded_events[last_complete_idx + 1 :] if e.get("event_type") == "state_transition"
        ]
        if len(transitions_after) > 1 and (
            last_handoff_idx is None or last_handoff_idx < last_complete_idx
        ):
            issues.append("continued_after_worker_without_handoff")

    ok = not issues
    return {
        "ok": ok,
        "issue_count": len(issues),
        "issues": issues,
        "run_id": state.get("run_id"),
        "current_step": state.get("current_step"),
        "session_stop_hints": list(stop_hints),
    }
