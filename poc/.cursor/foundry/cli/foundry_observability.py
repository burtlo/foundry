"""Phase 10 observability: receipts, events, status surface, and run metrics."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import foundry_protocol

IDENTITY_RECEIPT_KEYS = frozenset({"schema_version", "receipt_id", "run_id", "timestamp", "agent", "work_item_id"})
CRAFT_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "outputs",
        "exploration",
        "decisions",
        "commands",
        "blockers",
        "recommended_next_state",
        "state_patch",
        "parent_receipt_id",
    }
)
AGENT_CRAFT_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "packets" / "agent-craft.schema.json"
FORBIDDEN_RECEIPT_KEYS = frozenset(
    {
        "transcript",
        "model_turns",
        "full_response",
        "raw_output",
        "messages",
        "conversation",
        "turns",
        "chat_history",
        "tool_calls",
    }
)

STATUS_ICONS = {
    "completed": "✓",
    "in_progress": "🔄",
    "skipped": "—",
    "failed": "✗",
    "pending": "·",
}


def _step_worker_agent(step: dict[str, Any]) -> str | None:
    worker = step.get("worker")
    if isinstance(worker, dict):
        contract = worker.get("contract")
        if isinstance(contract, str) and contract.strip():
            return foundry_protocol.contract_id_from_path(contract)
        agent = worker.get("agent")
        if isinstance(agent, str) and agent.strip():
            return agent.strip()
    subagent = step.get("subagent")
    if subagent in (None, "", False):
        return None
    return str(subagent)


def parse_step_id(step_id: str) -> dict[str, str]:
    """Split a dotted step ID into phase (first segment) and step (remainder).

    Examples: shape.examine -> {phase: shape, step: examine}; deliver.stub -> {phase: deliver, step: stub}
    """
    text = str(step_id or "").strip()
    if not text:
        return {"phase": "", "step": ""}
    if "." not in text:
        return {"phase": text, "step": ""}
    phase, step = text.split(".", 1)
    return {"phase": phase, "step": step}


def phases_for_flow(flow: dict[str, Any]) -> list[str]:
    """Ordered unique phase prefixes for all steps in the flow."""
    seen: list[str] = []
    for step_id in ordered_flow_steps(flow):
        phase = parse_step_id(step_id)["phase"]
        if phase and phase not in seen:
            seen.append(phase)
    return seen

HUMAN_GATE_KINDS = frozenset({"human_approval", "human_confirm", "two_turn_stop"})
BUILDER_AGENT_NAMES = frozenset({"backend-builder", "client-builder", "feature-builder", "repairer"})


class ObservabilityError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        required_input: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.required_input = required_input
        self.extra = extra or {}


def short_receipt_id(receipt_id: str | None) -> str:
    if not receipt_id:
        return "—"
    return receipt_id[:4] + "…"


def parse_iso_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def load_events(events_path: Path) -> list[dict[str, Any]]:
    if not events_path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        item = json.loads(stripped)
        if isinstance(item, dict):
            events.append(item)
    return events


def tail_events(events_path: Path, count: int) -> list[dict[str, Any]]:
    events = load_events(events_path)
    if count <= 0:
        return []
    return events[-count:]


def validate_receipt_durable(receipt: dict[str, Any], *, path: str = "<receipt>") -> list[str]:
    issues: list[str] = []

    def walk(value: Any, prefix: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                dotted = f"{prefix}.{key}" if prefix else key
                if key in FORBIDDEN_RECEIPT_KEYS:
                    issues.append(f"{dotted}: telemetry field not allowed in durable receipts")
                walk(child, dotted)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{prefix}[{index}]")

    walk(receipt, path)
    return issues


def receipt_summary_markdown(receipt: dict[str, Any]) -> str:
    agent = receipt.get("agent") if isinstance(receipt.get("agent"), dict) else {}
    outputs = receipt.get("outputs") if isinstance(receipt.get("outputs"), dict) else {}
    commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []
    files_changed = outputs.get("files_changed") if isinstance(outputs.get("files_changed"), list) else []
    summary = str(outputs.get("summary_markdown") or "").strip()
    if not summary:
        exploration = receipt.get("exploration") if isinstance(receipt.get("exploration"), dict) else {}
        examined = exploration.get("files_examined") if isinstance(exploration.get("files_examined"), list) else []
        if examined:
            summary = f"Examined {len(examined)} file(s)."
    lines = [
        f"# Receipt {receipt.get('receipt_id')}",
        "",
        f"- Agent: {agent.get('name')} ({agent.get('mode')})",
        f"- Status: {receipt.get('status')}",
        f"- Work item: {receipt.get('work_item_id') or '—'}",
        f"- Recommended next: {receipt.get('recommended_next_state')}",
    ]
    if summary:
        lines.extend(["", "## Summary", summary])
    if files_changed:
        lines.extend(["", "## Files changed", *[f"- {path}" for path in files_changed]])
    if commands:
        lines.extend(
            [
                "",
                "## Commands",
                *[f"- `{item.get('command')}` exit {item.get('exit_code')}" for item in commands if isinstance(item, dict)],
            ]
        )
    blockers = receipt.get("blockers") if isinstance(receipt.get("blockers"), list) else []
    if blockers:
        lines.extend(["", "## Blockers", *[f"- {item}" for item in blockers]])
    return "\n".join(lines).strip() + "\n"


def load_receipt_file(receipts_dir: Path, receipt_id: str) -> dict[str, Any]:
    path = receipts_dir / f"{receipt_id}.json"
    if not path.is_file():
        raise ObservabilityError(
            "MISSING_RECEIPT",
            f"Receipt not found: {path}",
            required_input="receipt_id",
            extra={"receipt_id": receipt_id},
        )
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise ObservabilityError("INVALID_RECEIPT", f"Receipt at {path} is not a JSON object.")
    return receipt


def find_receipt_path(receipts_dir: Path, receipt_id: str) -> Path:
    direct = receipts_dir / f"{receipt_id}.json"
    if direct.is_file():
        return direct
    if receipts_dir.is_dir():
        for candidate in receipts_dir.glob("*.json"):
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("receipt_id") == receipt_id:
                return candidate
    raise ObservabilityError(
        "MISSING_RECEIPT",
        f"Receipt {receipt_id!r} not found under {receipts_dir}",
        required_input="receipt_id",
    )


def ordered_flow_steps(flow: dict[str, Any]) -> list[str]:
    steps = flow.get("steps") or {}
    if not isinstance(steps, dict):
        return []
    entry = flow.get("entry")
    if not isinstance(entry, str):
        return sorted(steps)
    ordered: list[str] = []
    seen: set[str] = set()
    queue = [entry]
    while queue:
        step_id = queue.pop(0)
        if step_id in seen:
            continue
        seen.add(step_id)
        ordered.append(step_id)
        for edge in flow.get("edges") or []:
            if isinstance(edge, dict) and edge.get("from") == step_id:
                target = edge.get("to")
                if isinstance(target, str) and target not in seen:
                    queue.append(target)
    for step_id in sorted(steps):
        if step_id not in seen:
            ordered.append(step_id)
    return ordered


def step_status_label(step_id: str, evidence: dict[str, Any], rework: dict[str, Any] | None) -> str:
    status = evidence.get("status") or "pending"
    icon = STATUS_ICONS.get(str(status), "·")
    if step_id == "implement.pre_pr_review" and rework:
        loops = int(rework.get("builder_to_bugbot_loops") or 0)
        if loops > 0 and status == "in_progress":
            return f"{icon} cycle {loops + 1}"
    if step_id == "implement.validate" and rework:
        loops = int(rework.get("validator_loops") or 0)
        if loops > 0 and status == "in_progress":
            return f"{icon} cycle {loops + 1}"
    return icon


def infer_next_hint(
    state: dict[str, Any],
    flow: dict[str, Any],
    *,
    compute_next: Callable[..., dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
    state_path: Path | None = None,
) -> str | None:
    if state.get("blocked"):
        return None
    if compute_next is None or state_path is None or config is None:
        current = state.get("current_step")
        step = (flow.get("steps") or {}).get(current) if isinstance(current, str) else None
        if isinstance(step, dict):
            agent = _step_worker_agent(step)
            if agent:
                return f"{agent} on step {current}"
        return None
    try:
        payload = compute_next(state_path, None, None, None)
    except Exception:
        return None
    next_step = payload.get("next_step")
    if not next_step:
        return None
    step = (flow.get("steps") or {}).get(next_step) or {}
    subagent = _step_worker_agent(step if isinstance(step, dict) else {})
    if subagent:
        return f"{subagent} on {next_step}"
    return f"advance to {next_step}"


def build_status_payload(
    state: dict[str, Any],
    events_path: Path,
    *,
    recent_event_count: int = 5,
    flow: dict[str, Any] | None = None,
    compute_next: Callable[..., dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
    state_path: Path | None = None,
) -> dict[str, Any]:
    blocked = state.get("blocked")
    recent_events = tail_events(events_path, recent_event_count)
    current_step = state.get("current_step")
    step_parts = (
        parse_step_id(str(current_step))
        if isinstance(current_step, str) and current_step
        else {"phase": "", "step": ""}
    )
    payload: dict[str, Any] = {
        "run_id": state.get("run_id"),
        "issue_key": state.get("issue_key"),
        "current_step": current_step,
        "phase": step_parts["phase"] or None,
        "step": step_parts["step"] or None,
        "risk_tier": state.get("risk_tier"),
        "factory_version": state.get("factory_version"),
        "blocked": blocked,
        "rework": state.get("rework"),
        "recent_events": recent_events,
        "receipt_count": len(state.get("receipt_ids") or []),
        "incomplete": blocked is None and state.get("pr_url") is None,
    }
    if flow is not None:
        payload["next_hint"] = infer_next_hint(
            state,
            flow,
            compute_next=compute_next,
            config=config,
            state_path=state_path,
        )
    return payload


def render_status_markdown(
    state: dict[str, Any],
    flow: dict[str, Any],
    run_dir: Path,
    *,
    compute_next: Callable[..., dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
    state_path: Path | None = None,
) -> str:
    issue_key = state.get("issue_key") or state.get("run_id")
    current_step = state.get("current_step") or "unknown"
    current_parts = parse_step_id(current_step) if current_step != "unknown" else {"phase": "unknown", "step": ""}
    risk_tier = state.get("risk_tier") or "medium"
    lines = [
        f"# {issue_key} | {current_step} | {risk_tier} risk",
        "",
        f"**Phase:** {current_parts['phase']}"
        + (f" · **Step:** {current_parts['step']}" if current_parts["step"] else ""),
        "",
    ]
    steps = state.get("steps") if isinstance(state.get("steps"), dict) else {}
    rework = state.get("rework") if isinstance(state.get("rework"), dict) else {}
    graph_path = run_dir / "execution-graph.json"
    work_items: dict[str, str] = {}
    if graph_path.is_file():
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            for item in graph.get("work_items") or []:
                if isinstance(item, dict) and item.get("id"):
                    receipt_id = item.get("receipt_id")
                    work_items[str(item["id"])] = short_receipt_id(receipt_id) if receipt_id else "—"
        except json.JSONDecodeError:
            pass

    steps_by_phase: dict[str, list[str]] = {}
    for step_id in ordered_flow_steps(flow):
        phase = parse_step_id(step_id)["phase"] or step_id
        steps_by_phase.setdefault(phase, []).append(step_id)

    for phase in phases_for_flow(flow):
        lines.extend([f"## {phase}", "", "| Step | Status | Receipt |", "|------|--------|---------|"])
        for step_id in steps_by_phase.get(phase, []):
            evidence = steps.get(step_id) if isinstance(steps.get(step_id), dict) else {}
            label = step_status_label(step_id, evidence, rework)
            receipt_id = evidence.get("receipt_id")
            lines.append(f"| {step_id} | {label} | {short_receipt_id(receipt_id)} |")
        lines.append("")

    if work_items:
        lines.extend(["## build graph", "", "| Work item | Status | Receipt |", "|-----------|--------|---------|"])
        for work_item_id, receipt in work_items.items():
            lines.append(f"| {work_item_id} | ✓ | {receipt} |")
        lines.append("")

    blocked = state.get("blocked")
    if isinstance(blocked, dict) and blocked.get("reason"):
        lines.extend(["", f"**Blocker:** {blocked['reason']}"])
    next_hint = infer_next_hint(
        state,
        flow,
        compute_next=compute_next,
        config=config,
        state_path=state_path,
    )
    if next_hint:
        lines.extend(["", f"**Next:** {next_hint}"])
    return "\n".join(lines).strip() + "\n"


def gate_presented_for_step(events: list[dict[str, Any]], step_id: str) -> bool:
    return any(
        event.get("event_type") == "gate_presented" and event.get("step_id") == step_id for event in events
    )


def subagent_invocation_metrics(events: list[dict[str, Any]]) -> dict[str, int]:
    launch_ids: set[str] = set()
    completed_launch_ids: set[str] = set()
    orphan_completions = 0
    launched = 0
    completed = 0
    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        event_type = event.get("event_type")
        if event_type == "subagent_launched":
            launched += 1
            launch_id = payload.get("launch_id")
            if isinstance(launch_id, str):
                launch_ids.add(launch_id)
        elif event_type in ("subagent_completed", "subagent_failed"):
            completed += 1
            launch_id = payload.get("launch_id")
            if isinstance(launch_id, str):
                if launch_id not in launch_ids:
                    orphan_completions += 1
                completed_launch_ids.add(launch_id)
            else:
                orphan_completions += 1
    return {
        "launched": launched,
        "completed": completed,
        "orphan_completions": orphan_completions,
        "orphan_launches": len(launch_ids - completed_launch_ids),
    }


def receipt_has_builder_evidence(receipt: dict[str, Any]) -> bool:
    outputs = receipt.get("outputs") if isinstance(receipt.get("outputs"), dict) else {}
    files_changed = outputs.get("files_changed") if isinstance(outputs.get("files_changed"), list) else []
    if files_changed:
        return True
    commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []
    return any(isinstance(item, dict) and item.get("exit_code") == 0 for item in commands)


def validate_receipt_semantic(receipt: dict[str, Any], *, path: str = "<receipt>") -> list[str]:
    issues: list[str] = []
    agent_info = receipt.get("agent") if isinstance(receipt.get("agent"), dict) else {}
    agent_name = agent_info.get("name")
    outputs = receipt.get("outputs") if isinstance(receipt.get("outputs"), dict) else {}

    if agent_name in BUILDER_AGENT_NAMES:
        if not receipt_has_builder_evidence(receipt):
            issues.append(f"{path}: builder receipt requires files_changed or successful commands")

    if agent_name == "implementation-validator":
        findings = outputs.get("findings")
        has_counts = any(outputs.get(key) for key in ("critical_count", "important_count", "minor_count"))
        if has_counts and not isinstance(findings, list):
            issues.append(f"{path}: validator receipt with counts must include outputs.findings[]")
        elif isinstance(findings, list) and not findings and has_counts:
            issues.append(f"{path}: validator outputs.findings[] is empty while severity counts are set")

    if agent_name in ("pre-pr-review", "bugbot", "security-review"):
        findings = outputs.get("findings")
        has_highs = any(outputs.get(key) for key in ("bugbot_high", "security_high", "high_count"))
        if has_highs and not isinstance(findings, list):
            issues.append(f"{path}: review receipt with high findings must include outputs.findings[]")

    return issues


def command_cost_summary(run_dir: Path, receipt_ids: list[str]) -> dict[str, Any]:
    receipts_dir = run_dir / "receipts"
    commands: list[dict[str, Any]] = []
    total_ms = 0
    for receipt_id in receipt_ids:
        path = receipts_dir / f"{receipt_id}.json"
        if not path.is_file():
            continue
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(receipt, dict):
            continue
        for item in receipt.get("commands") or []:
            if not isinstance(item, dict):
                continue
            duration = item.get("duration_ms")
            if isinstance(duration, int):
                total_ms += duration
            commands.append(
                {
                    "receipt_id": receipt_id,
                    "command": item.get("command"),
                    "exit_code": item.get("exit_code"),
                    "duration_ms": duration,
                }
            )
    return {
        "command_count": len(commands),
        "total_duration_ms": total_ms,
        "commands": commands,
    }


def load_cursor_telemetry(run_dir: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "session": None,
        "usage": None,
        "tool_events": [],
    }
    session_path = run_dir / "cursor-session.json"
    if session_path.is_file():
        try:
            session = json.loads(session_path.read_text(encoding="utf-8"))
            if isinstance(session, dict):
                payload["session"] = session
        except json.JSONDecodeError:
            pass
    usage_path = run_dir / "cursor-usage.json"
    if usage_path.is_file():
        try:
            usage = json.loads(usage_path.read_text(encoding="utf-8"))
            if isinstance(usage, dict):
                payload["usage"] = usage
        except json.JSONDecodeError:
            pass
    telemetry_path = run_dir / "cursor-telemetry.jsonl"
    if telemetry_path.is_file():
        tool_events: list[dict[str, Any]] = []
        tool_duration_ms = 0
        tool_count = 0
        for line in telemetry_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                item = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                tool_events.append(item)
                tool_count += 1
                duration = item.get("duration_ms")
                if isinstance(duration, (int, float)):
                    tool_duration_ms += int(duration)
        payload["tool_events"] = tool_events
        payload["tool_summary"] = {
            "event_count": tool_count,
            "total_duration_ms": tool_duration_ms,
        }
    return payload


def gate_wait_ms(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    waits: list[dict[str, Any]] = []
    presented_at: dict[str, datetime] = {}
    for event in events:
        event_type = event.get("event_type")
        step_id = event.get("step_id")
        timestamp = event.get("timestamp")
        if not isinstance(step_id, str) or not isinstance(timestamp, str):
            continue
        if event_type == "gate_presented":
            presented_at[step_id] = parse_iso_timestamp(timestamp)
        if event_type == "gate_resolved" and step_id in presented_at:
            resolved_at = parse_iso_timestamp(timestamp)
            wait_ms = int((resolved_at - presented_at[step_id]).total_seconds() * 1000)
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            waits.append(
                {
                    "step_id": step_id,
                    "wait_ms": max(wait_ms, 0),
                    "decision": payload.get("decision"),
                    "material_change": payload.get("material_change"),
                }
            )
    return waits


def summarize_metrics(
    state: dict[str, Any],
    events_path: Path,
    run_dir: Path,
) -> dict[str, Any]:
    events = load_events(events_path)
    rework = state.get("rework") if isinstance(state.get("rework"), dict) else {}
    gate_waits = gate_wait_ms(events)
    gate_resolved_all = [
        event
        for event in events
        if event.get("event_type") == "gate_resolved"
    ]
    gate_resolved = [
        event
        for event in gate_resolved_all
        if (
            (event.get("payload") or {}).get("gate_source")
            or (event.get("payload") or {}).get("source")
            or "human"
        )
        == "human"
    ]
    material_gate_changes = sum(
        1
        for event in gate_resolved
        if isinstance(event.get("payload"), dict) and event["payload"].get("material_change")
    )
    if not material_gate_changes:
        material_gate_changes = sum(
            1
            for event in gate_resolved
            if isinstance(event.get("payload"), dict)
            and str(event["payload"].get("decision")) not in {"approve", "pass", "post", "skip", "accept_risk"}
        )

    grilling_decisions = sum(
        1
        for event in events
        if event.get("event_type") == "gate_resolved"
        and event.get("step_id") == "intake.grill"
    )
    approved_ac_version = int(state.get("approved_ac_version") or 0)

    plan_stability = None
    graph_path = run_dir / "execution-graph.json"
    if graph_path.is_file():
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            if isinstance(graph.get("plan_stability"), dict):
                plan_stability = graph["plan_stability"]
        except json.JSONDecodeError:
            plan_stability = None

    cli_commands = [
        event
        for event in events
        if event.get("event_type") == "cli_invoked"
    ]
    failure_classes: dict[str, int] = {}
    for event in events:
        if event.get("event_type") != "failure_classified":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        failure_class = payload.get("failure_class")
        if isinstance(failure_class, str):
            failure_classes[failure_class] = failure_classes.get(failure_class, 0) + 1

    invocation = subagent_invocation_metrics(events)
    receipt_ids = state.get("receipt_ids") if isinstance(state.get("receipt_ids"), list) else []
    command_cost = command_cost_summary(run_dir, [str(item) for item in receipt_ids])
    cursor_telemetry = load_cursor_telemetry(run_dir)
    gate_presented_count = sum(1 for event in events if event.get("event_type") == "gate_presented")

    return {
        "run_id": state.get("run_id"),
        "issue_key": state.get("issue_key"),
        "factory_version": state.get("factory_version"),
        "rework": rework,
        "gate_wait_times_ms": gate_waits,
        "gate_utility": {
            "resolved_count": len(gate_resolved),
            "total_resolved_count": len(gate_resolved_all),
            "material_change_count": material_gate_changes,
        },
        "clarification_yield": {
            "approved_ac_version": approved_ac_version,
            "grilling_gate_resolutions": grilling_decisions,
        },
        "plan_stability": plan_stability,
        "cli_adoption": {
            "cli_invoked_count": len(cli_commands),
            "commands": [
                (event.get("payload") or {}).get("command")
                for event in cli_commands
                if isinstance(event.get("payload"), dict)
            ],
        },
        "failure_class_distribution": failure_classes,
        "subagent_invocations": invocation,
        "gate_presented_count": gate_presented_count,
        "command_cost": command_cost,
        "cursor_telemetry": {
            "conversation_id": (cursor_telemetry.get("session") or {}).get("conversation_id"),
            "usage": cursor_telemetry.get("usage"),
            "tool_summary": cursor_telemetry.get("tool_summary"),
        },
        "brief_snapshot": state.get("brief_snapshot"),
    }


def export_metrics(
    state: dict[str, Any],
    events_path: Path,
    run_dir: Path,
) -> dict[str, Any]:
    metrics = summarize_metrics(state, events_path, run_dir)
    return {
        "schema_version": foundry_protocol.PROTOCOL_VERSION,
        "artifact": "foundry-run-metrics",
        "run_id": state.get("run_id"),
        "issue_key": state.get("issue_key"),
        "factory_version": state.get("factory_version"),
        "metrics": metrics,
    }


def receipt_staging_path(run_dir: Path, launch_id: str) -> Path:
    return receipt_craft_path(run_dir, launch_id)


def receipt_meta_path(run_dir: Path, launch_id: str) -> Path:
    return run_dir / "staging" / f"{launch_id}.meta.json"


def receipt_craft_path(run_dir: Path, launch_id: str) -> Path:
    return run_dir / "staging" / f"{launch_id}.craft.json"


def write_launch_meta(run_dir: Path, launch_id: str, scaffold: dict[str, Any]) -> Path:
    meta = {
        "schema_version": foundry_protocol.PROTOCOL_VERSION,
        "launch_id": launch_id,
        "receipt_id": scaffold["receipt_id"],
        "run_id": scaffold["run_id"],
        "timestamp": scaffold["timestamp"],
        "agent": scaffold["agent"],
        "step_id": scaffold.get("step_id"),
        "work_item_id": scaffold.get("work_item_id"),
    }
    for key in ("branch_point", "reviewed_head_sha"):
        if scaffold.get(key):
            meta[key] = scaffold[key]
    path = receipt_meta_path(run_dir, launch_id)
    path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return path


def load_launch_meta(run_dir: Path, launch_id: str) -> dict[str, Any]:
    path = receipt_meta_path(run_dir, launch_id)
    if not path.is_file():
        raise ObservabilityError(
            "RECEIPT_META_MISSING",
            f"Launch meta not found: {path}",
            required_input="launch-id",
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ObservabilityError("INVALID_RECEIPT", f"Meta at {path} is not a JSON object.")
    return data


def extract_craft_fields(payload: dict[str, Any]) -> dict[str, Any]:
    craft: dict[str, Any] = {}
    for key in CRAFT_RECEIPT_KEYS:
        if key in payload:
            craft[key] = payload[key]
    return craft


def validate_craft_overlay(craft: dict[str, Any]) -> None:
    """Validate craft-only overlay against agent-craft.schema.json when present."""
    if not craft:
        return
    if not AGENT_CRAFT_SCHEMA_PATH.is_file():
        return
    try:
        from jsonschema import Draft202012Validator
    except ImportError:  # pragma: no cover
        return
    schema = json.loads(AGENT_CRAFT_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(craft), key=str)
    if errors:
        messages = [
            f"{'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        ]
        raise ObservabilityError(
            "INVALID_CRAFT_OVERLAY",
            "Craft overlay failed agent-craft.schema.json.",
            extra={"errors": messages},
        )


def merge_engine_receipt(
    *,
    meta: dict[str, Any],
    craft: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    """Build durable receipt: engine identity + craft overlay; restamp timestamp at complete."""
    agent = meta.get("agent") if isinstance(meta.get("agent"), dict) else {"name": "unknown", "mode": "unknown"}
    receipt: dict[str, Any] = {
        "schema_version": foundry_protocol.PROTOCOL_VERSION,
        "receipt_id": meta["receipt_id"],
        "run_id": run_id,
        "timestamp": _now_iso(),
        "agent": {"name": agent.get("name"), "mode": agent.get("mode")},
        "status": craft.get("status") or "completed",
        "work_item_id": meta.get("work_item_id"),
        "input_digests": meta.get("input_digests") or {},
        "context_usage": meta.get("context_usage") or {},
        "outputs": craft.get("outputs") if isinstance(craft.get("outputs"), dict) else {},
        "recommended_next_state": str(craft.get("recommended_next_state") or ""),
        "provenance": {
            "source": "worker_launch",
            "launch_id": meta["launch_id"],
            "run_id": run_id,
            "step_id": meta.get("step_id"),
            "agent": agent.get("name"),
            "mode": agent.get("mode"),
        },
    }
    for key in ("branch_point", "reviewed_head_sha"):
        if meta.get(key):
            receipt["provenance"][key] = meta[key]
    for key in ("exploration", "decisions", "commands", "blockers", "state_patch", "parent_receipt_id"):
        if key in craft:
            receipt[key] = craft[key]
    return receipt


def assert_scaffold_identity(staging_receipt: dict[str, Any], meta: dict[str, Any]) -> None:
    """Reject tampering of engine-owned identity fields on the staging scaffold."""
    for key in ("receipt_id", "run_id"):
        if staging_receipt.get(key) != meta.get(key):
            raise ObservabilityError(
                "RECEIPT_SCAFFOLD_TAMPER",
                f"Staging {key} does not match launch meta (engine-owned).",
                extra={"expected": meta.get(key), "actual": staging_receipt.get(key)},
            )
    staging_agent = staging_receipt.get("agent") if isinstance(staging_receipt.get("agent"), dict) else {}
    meta_agent = meta.get("agent") if isinstance(meta.get("agent"), dict) else {}
    if staging_agent.get("name") != meta_agent.get("name") or staging_agent.get("mode") != meta_agent.get("mode"):
        raise ObservabilityError(
            "RECEIPT_SCAFFOLD_TAMPER",
            "Staging agent does not match launch meta (engine-owned).",
            extra={"expected": meta_agent, "actual": staging_agent},
        )


def assert_receipt_staging_path(
    receipt_path: Path,
    receipts_dir: Path,
    expected_staging_path: Path,
) -> None:
    resolved = receipt_path.resolve()
    try:
        resolved.relative_to(receipts_dir.resolve())
        raise ObservabilityError(
            "RECEIPT_PARENT_AUTHORED",
            "Receipt path must not be under receipts/. The worker writes craft-only JSON to craft_staging_path.",
            required_input="receipt",
        )
    except ValueError:
        pass
    if resolved != expected_staging_path.resolve():
        raise ObservabilityError(
            "RECEIPT_STAGING_MISMATCH",
            f"Receipt must be the craft_staging_path from launch: {expected_staging_path}",
            required_input="receipt",
            extra={"expected": str(expected_staging_path), "actual": str(receipt_path)},
        )


def ensure_receipt_in_run(
    receipt_path: Path,
    receipts_dir: Path,
    run_id: str,
    *,
    launch_id: str | None = None,
    run_dir: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    receipt_raw = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(receipt_raw, dict):
        raise ObservabilityError("INVALID_RECEIPT", f"Receipt at {receipt_path} is not a JSON object.")

    directory = run_dir or receipts_dir.parent
    resolved_launch = launch_id
    under_staging = False
    try:
        receipt_path.resolve().relative_to((directory / "staging").resolve())
        under_staging = True
    except (ValueError, OSError):
        under_staging = False

    if not resolved_launch and under_staging and receipt_path.name.endswith(".craft.json"):
        stem = receipt_path.name
        resolved_launch = stem[: -len(".craft.json")]

    if resolved_launch and under_staging:
        meta = load_launch_meta(directory, resolved_launch)
        craft_path = receipt_craft_path(directory, resolved_launch)
        expected_staging = receipt_staging_path(directory, resolved_launch)
        if receipt_path.resolve() != expected_staging.resolve():
            raise ObservabilityError(
                "RECEIPT_STAGING_MISMATCH",
                f"Receipt must be the craft_staging_path from launch: {expected_staging}",
                required_input="receipt",
            )
        validate_craft_overlay(receipt_raw)
        craft = extract_craft_fields(receipt_raw)
        receipt = merge_engine_receipt(meta=meta, craft=craft, run_id=run_id)
        try:
            foundry_protocol.validate_receipt_contract(
                receipt,
                expected_run_id=run_id,
                expected_launch_id=resolved_launch,
                expected_step_id=str(meta.get("step_id") or ""),
                expected_agent=str((meta.get("agent") or {}).get("name") or ""),
                expected_mode=str((meta.get("agent") or {}).get("mode") or ""),
            )
        except foundry_protocol.ProtocolError as exc:
            raise ObservabilityError(exc.error_code, exc.message, extra={"errors": exc.errors}) from exc
    elif resolved_launch and not under_staging:
        # Explicit launch_id with non-staging path: still merge from meta if present
        meta_path = receipt_meta_path(directory, resolved_launch)
        if meta_path.is_file():
            meta = load_launch_meta(directory, resolved_launch)
            craft = extract_craft_fields(receipt_raw)
            validate_craft_overlay(craft)
            receipt = merge_engine_receipt(meta=meta, craft=craft, run_id=run_id)
        else:
            receipt = dict(receipt_raw)
            receipt["run_id"] = run_id
            receipt["timestamp"] = _now_iso()
    else:
        # Evidence files / legacy receipts outside staging: copy through, restamp timestamp
        receipt = dict(receipt_raw)
        receipt["run_id"] = run_id
        receipt["timestamp"] = _now_iso()
        if not receipt.get("receipt_id"):
            raise ObservabilityError("INVALID_RECEIPT", "Receipt is missing receipt_id.", required_input="receipt_id")

    issues = validate_receipt_durable(receipt, path=str(receipt_path))
    if issues:
        raise ObservabilityError(
            "RECEIPT_TELEMETRY_FORBIDDEN",
            "Receipt contains telemetry fields that must not be persisted.",
            extra={"issues": issues},
        )
    receipt_id = receipt.get("receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id:
        raise ObservabilityError("INVALID_RECEIPT", "Receipt is missing receipt_id.", required_input="receipt_id")
    destination = receipts_dir / f"{receipt_id}.json"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt, destination


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def subagent_launch(
    *,
    run_id: str,
    run_dir: Path,
    events_path: Path,
    step_id: str | None,
    agent: str,
    mode: str,
    work_item_id: str | None,
    append_event: Callable[[Path, dict[str, Any]], None],
    make_event: Callable[..., dict[str, Any]],
    emit_events: bool,
    launch_id: str | None = None,
    receipt_id: str | None = None,
    branch_point: str | None = None,
    reviewed_head_sha: str | None = None,
) -> dict[str, Any]:
    launch_id = launch_id or str(uuid4())
    craft_path = receipt_craft_path(run_dir, launch_id)
    craft_path.parent.mkdir(parents=True, exist_ok=True)
    scaffold = {
        "schema_version": foundry_protocol.PROTOCOL_VERSION,
        "receipt_id": receipt_id or str(uuid4()),
        "run_id": run_id,
        "timestamp": _now_iso(),
        "agent": {"name": agent, "mode": mode},
        "step_id": step_id,
        "work_item_id": work_item_id,
    }
    if branch_point:
        scaffold["branch_point"] = branch_point
    if reviewed_head_sha:
        scaffold["reviewed_head_sha"] = reviewed_head_sha
    meta_path = write_launch_meta(run_dir, launch_id, scaffold)
    if emit_events:
        append_event(
            events_path,
            make_event(
                run_id,
                "subagent_launched",
                "parent",
                step_id=step_id,
                payload={
                    "launch_id": launch_id,
                    "agent": agent,
                    "mode": mode,
                    "work_item_id": work_item_id,
                    "receipt_meta_path": str(meta_path),
                    "craft_staging_path": str(craft_path),
                },
            ),
        )
    return {
        "launch_id": launch_id,
        "receipt_id": scaffold["receipt_id"],
        "timestamp": scaffold["timestamp"],
        "receipt_meta_path": str(meta_path),
        "craft_staging_path": str(craft_path),
        "step_id": step_id,
        "agent": agent,
        "mode": mode,
        "work_item_id": work_item_id,
    }


def subagent_complete(
    *,
    run_id: str,
    events_path: Path,
    receipts_dir: Path,
    receipt_path: Path,
    launch_id: str | None,
    step_id: str | None,
    state: dict[str, Any],
    append_event: Callable[[Path, dict[str, Any]], None],
    make_event: Callable[..., dict[str, Any]],
    emit_events: bool,
) -> dict[str, Any]:
    receipt, stored_path = ensure_receipt_in_run(
        receipt_path,
        receipts_dir,
        run_id,
        launch_id=launch_id,
        run_dir=receipts_dir.parent,
    )
    semantic_issues = validate_receipt_semantic(receipt, path=str(stored_path))
    if semantic_issues:
        raise ObservabilityError(
            "RECEIPT_SEMANTIC_INVALID",
            "Receipt failed semantic validation.",
            extra={"issues": semantic_issues},
        )
    receipt_id = str(receipt["receipt_id"])
    ids = state.setdefault("receipt_ids", [])
    if receipt_id not in ids:
        ids.append(receipt_id)

    agent = (receipt.get("agent") or {}).get("name")
    status = receipt.get("status")
    event_type = "subagent_completed"
    if status == "failed":
        event_type = "subagent_failed"
    elif status == "partial":
        event_type = "subagent_completed"

    if emit_events:
        append_event(
            events_path,
            make_event(
                run_id,
                event_type,
                "subagent",
                step_id=step_id,
                payload={
                    "launch_id": launch_id,
                    "receipt_id": receipt_id,
                    "agent": agent,
                    "status": status,
                    "work_item_id": receipt.get("work_item_id"),
                },
            ),
        )
        append_event(
            events_path,
            make_event(
                run_id,
                "evidence_recorded",
                "parent",
                step_id=step_id,
                payload={"receipt_id": receipt_id, "receipt_path": str(stored_path)},
            ),
        )
    return {
        "receipt_id": receipt_id,
        "receipt_path": str(stored_path),
        "event_type": event_type,
        "formatted": receipt_summary_markdown(receipt),
    }


def log_cli_invoked(
    *,
    run_id: str,
    events_path: Path,
    command: str,
    argv: list[str],
    append_event: Callable[[Path, dict[str, Any]], None],
    make_event: Callable[..., dict[str, Any]],
    emit_events: bool,
    step_id: str | None = None,
    exit_code: int = 0,
    extra: dict[str, Any] | None = None,
) -> None:
    if not emit_events or not events_path.parent.is_dir():
        return
    event_type = "cli_invoked" if exit_code == 0 else "cli_failed"
    payload: dict[str, Any] = {
        "command": command,
        "argv": argv,
        "exit_code": exit_code,
    }
    if extra:
        payload.update(extra)
    append_event(
        events_path,
        make_event(
            run_id,
            event_type,
            "cli",
            step_id=step_id,
            payload=payload,
        ),
    )


def write_status_markdown(path: Path, markdown: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return str(path)
