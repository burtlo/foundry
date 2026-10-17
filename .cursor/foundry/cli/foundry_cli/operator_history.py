"""Operator-readable run history projection (independent of steward context packet)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.artifact_reads import resolve_nearest_sealed_ancestor_artifact
from foundry_cli.engine.agent.dispatch import agent_requests_map
from foundry_cli.engine.agent.tasks import SHAPE_EXAMINE_TASK_ID
from foundry_cli.engine.run_config import work_prompt_from_snapshot
from foundry_cli.engine.shape_step_executor import _examination_summary_markdown
from foundry_cli.ledger import ledger_events
from foundry_cli.parked_run import build_parked_run_projection
from foundry_cli.paths import resolve_run_uri
from foundry_cli.registry import get_node


def _snapshot_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    state = snapshot.get("state")
    return state if isinstance(state, dict) else {}


def _intake_text(snapshot: dict[str, Any]) -> str | None:
    state = _snapshot_state(snapshot)
    ticket = state.get("ticket")
    if isinstance(ticket, dict):
        raw = ticket.get("raw_input")
        if isinstance(raw, str) and raw.strip():
            return raw
    prompt = work_prompt_from_snapshot(snapshot)
    if prompt:
        return prompt
    return None


def _latest_examination_result(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    for record in agent_requests_map(snapshot).values():
        if not isinstance(record, dict):
            continue
        if record.get("task_id") != SHAPE_EXAMINE_TASK_ID or record.get("status") != "accepted":
            continue
        body = record.get("accepted_result")
        if isinstance(body, dict):
            latest = body
    return latest


def _model_response_markdown(snapshot: dict[str, Any]) -> str | None:
    result = _latest_examination_result(snapshot)
    if result is not None:
        text = _examination_summary_markdown(result).strip()
        return text or None

    state = _snapshot_state(snapshot)
    parts: list[str] = []
    draft_ac = state.get("draft_ac")
    if isinstance(draft_ac, str) and draft_ac.strip():
        parts.extend(["### Draft acceptance criteria", "", draft_ac.strip(), ""])
    assumptions = state.get("assumptions")
    if isinstance(assumptions, list) and assumptions:
        parts.append("### Assumptions")
        parts.append("")
        for item in assumptions:
            if isinstance(item, str) and item.strip():
                parts.append(f"- {item.strip()}")
        parts.append("")
    decisions = state.get("examination_decisions")
    if isinstance(decisions, list) and decisions:
        parts.append("### Examination decisions")
        parts.append("")
        for item in decisions:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            basis = str(item.get("basis") or "").strip()
            if text:
                line = f"- {text}"
                if basis:
                    line = f"{line} _({basis})_"
                parts.append(line)
        parts.append("")
    if not parts:
        return None
    return "\n".join(parts).strip()


def clarifying_question_is_open(item: dict[str, Any]) -> bool:
    """True when the operator still needs to answer this clarifying question."""
    status = str(item.get("status", "open")).lower()
    return status not in ("resolved", "answered", "closed")


def format_clarifying_question_markdown(item: dict[str, Any]) -> str:
    """Markdown for one clarifying question (bold text, optional id metadata)."""
    qid = str(item.get("id") or "").strip()
    text = str(item.get("text") or "").strip()
    if not text:
        return f"*({qid})*" if qid else ""
    if qid:
        return f"**{text}** *({qid})*"
    return f"**{text}**"


def _questions_and_answers_markdown(snapshot: dict[str, Any]) -> str | None:
    state = _snapshot_state(snapshot)
    questions = state.get("clarifying_questions")
    if not isinstance(questions, list) or not questions:
        return None
    answers = state.get("clarifying_answers")
    answer_map: dict[str, str] = {}
    if isinstance(answers, dict):
        for key, value in answers.items():
            if value is not None:
                answer_map[str(key)] = str(value)

    lines: list[str] = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        if clarifying_question_is_open(item):
            continue
        qid = str(item.get("id") or "")
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        lines.append(format_clarifying_question_markdown(item))
        if qid and qid in answer_map and answer_map[qid].strip():
            lines.append("")
            lines.append(f"> {answer_map[qid].strip()}")
        elif qid and qid in answer_map:
            lines.append("")
            lines.append("> _No answer recorded._")
        lines.append("")
    if not lines:
        return None
    return "\n".join(lines).strip()


def _gate_decision_events(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for event in ledger_events(snapshot):
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event_type == "gate.decided":
            decision = payload.get("decision")
            if decision is not None:
                collected.append(
                    {
                        "decision": str(decision),
                        "node_id": str(event.get("node_id") or ""),
                        "decider": str(payload.get("decider") or "engine"),
                    }
                )
            continue
        if event_type == "gate.resolved" and str(payload.get("decider") or "") == "user":
            decision = payload.get("decision")
            if decision is not None:
                collected.append(
                    {
                        "decision": str(decision),
                        "node_id": str(event.get("node_id") or ""),
                        "decider": "user",
                    }
                )
    return collected


def _decisions_markdown(snapshot: dict[str, Any]) -> str | None:
    events = _gate_decision_events(snapshot)
    if not events:
        return None
    lines: list[str] = []
    for item in events:
        node_id = item.get("node_id") or "gate"
        decision = item.get("decision") or ""
        lines.append(f"- **{node_id}:** {decision}")
    return "\n".join(lines)


def _active_visit(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    active = snapshot.get("active_visit")
    return active if isinstance(active, dict) else None


def _presentation_markdown(
    snapshot: dict[str, Any],
    *,
    run_dir: Path,
    from_visit_id: str,
) -> str | None:
    match = resolve_nearest_sealed_ancestor_artifact(
        snapshot,
        qualified_ref="shape.present.presentation",
        from_visit_id=from_visit_id,
        run_dir=run_dir,
    )
    if match:
        path = Path(match["resolved_path"])
        if path.is_file():
            return path.read_text(encoding="utf-8").strip() or None

    state = _snapshot_state(snapshot)
    uri = state.get("presentation_artifact_path")
    if isinstance(uri, str) and uri.startswith("run:"):
        try:
            path = resolve_run_uri(uri, run_dir, from_visit_id)
            if path.is_file():
                return path.read_text(encoding="utf-8").strip() or None
        except (OSError, ValueError):
            pass
    return None


def _current_step_markdown(
    snapshot: dict[str, Any],
    flow: dict[str, Any],
    *,
    run_dir: Path,
) -> str | None:
    visit = _active_visit(snapshot)
    if visit is None:
        return None
    visit_id = str(visit.get("id") or "")
    node_id = str(visit.get("node_id") or "")
    if not visit_id or not node_id:
        return None

    wait = snapshot.get("wait")
    wait_kind = str(wait.get("kind") or "") if isinstance(wait, dict) else ""

    parts: list[str] = []
    try:
        node = get_node(flow, node_id)
    except KeyError:
        node = {}

    if str(node.get("kind")) == "gate":
        prompt = node.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            parts.extend([prompt.strip(), ""])

    presentation = _presentation_markdown(snapshot, run_dir=run_dir, from_visit_id=visit_id)
    if presentation:
        parts.extend(["", presentation, ""])

    state = _snapshot_state(snapshot)
    presented_ac = state.get("presented_ac")
    if isinstance(presented_ac, str) and presented_ac.strip() and wait_kind == "decision":
        parts.extend(["", "### Presented acceptance criteria", "", presented_ac.strip(), ""])

    if not parts:
        return None
    return "\n".join(parts).strip()


def _parked_section_markdown(parked: dict[str, Any]) -> str:
    """Body lines for a parked run — same fields as human ``foundry status`` (no commands)."""
    lines: list[str] = []
    step_title = parked.get("step_title")
    if step_title:
        lines.append(f"step={step_title}")
    node_id = parked.get("node_id")
    if node_id:
        lines.append(f"node={node_id}")
    reason_code = parked.get("reason_code")
    if isinstance(reason_code, str) and reason_code.strip():
        lines.append(f"code={reason_code.strip()}")
    message = parked.get("message")
    if isinstance(message, str) and message.strip():
        lines.append(message.strip())
    for finding in parked.get("findings") or []:
        if isinstance(finding, str) and finding.strip():
            lines.append(f"- {finding.strip()}")
    return "\n".join(lines)


def build_operator_history_sections(
    snapshot: dict[str, Any],
    flow: dict[str, Any],
    *,
    run_dir: Path,
) -> list[dict[str, Any]]:
    """Return ordered operator-history sections (JSON-serializable)."""
    sections: list[dict[str, Any]] = []

    intake = _intake_text(snapshot)
    if intake:
        sections.append({"kind": "intake", "markdown": intake})

    model = _model_response_markdown(snapshot)
    if model:
        sections.append({"kind": "model_response", "markdown": model})

    questions = _questions_and_answers_markdown(snapshot)
    if questions:
        sections.append({"kind": "questions", "markdown": questions})

    decisions = _decisions_markdown(snapshot)
    if decisions:
        sections.append({"kind": "decisions", "markdown": decisions})

    current = _current_step_markdown(snapshot, flow, run_dir=run_dir)
    if current:
        sections.append({"kind": "current_step", "markdown": current})

    parked = build_parked_run_projection(snapshot, flow, run_dir)
    if parked is not None:
        sections.append(
            {
                "kind": "parked",
                "heading": str(parked.get("heading") or "").strip(),
                "markdown": _parked_section_markdown(parked),
            }
        )

    return sections


_SECTION_HEADINGS = {
    "intake": "## Your request",
    "model_response": "## Model response",
    "questions": "## Questions and answers",
    "decisions": "## Decisions",
    "current_step": "## Approval material",
}


def render_operator_history_markdown(sections: list[dict[str, Any]]) -> str:
    """Compose operator history markdown from projection sections."""
    blocks: list[str] = []
    for section in sections:
        kind = str(section.get("kind") or "")
        body = str(section.get("markdown") or "").strip()
        if not body:
            continue
        custom_heading = section.get("heading")
        if custom_heading:
            heading = f"## {custom_heading}"
        else:
            heading = _SECTION_HEADINGS.get(kind)
        if heading:
            blocks.extend([heading, "", body, ""])
        else:
            blocks.extend([body, ""])
    return "\n".join(blocks).strip() + ("\n" if blocks else "")


def project_operator_history(
    snapshot: dict[str, Any],
    flow: dict[str, Any],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    sections = build_operator_history_sections(snapshot, flow, run_dir=run_dir)
    markdown = render_operator_history_markdown(sections)
    return {"sections": sections, "markdown": markdown}
