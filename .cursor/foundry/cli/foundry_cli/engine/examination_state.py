"""Examination state helpers (engine-derived fields)."""

from __future__ import annotations

from typing import Any

from foundry_cli.engine.wait_state import clear_run_wait, set_run_wait
from foundry_cli.ledger import append_event


def derive_open_clarifying_questions_count(state: dict[str, Any]) -> int:
    """Count unresolved clarifying questions; fall back to patched counter."""
    questions = state.get("clarifying_questions")
    if isinstance(questions, list):
        open_count = 0
        for item in questions:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "open")).lower()
            if status not in ("resolved", "answered", "closed"):
                open_count += 1
        return open_count
    count = state.get("open_clarifying_questions_count")
    if isinstance(count, bool):
        return 0
    if isinstance(count, (int, float)):
        return int(count)
    return 0


def sync_open_clarifying_questions_count(snapshot: dict[str, Any]) -> None:
    """Keep patched counter aligned when clarifying_questions records exist."""
    state = snapshot.get("state")
    if not isinstance(state, dict):
        return
    questions = state.get("clarifying_questions")
    if not isinstance(questions, list):
        return
    state["open_clarifying_questions_count"] = derive_open_clarifying_questions_count(state)


def _open_question_ids(state: dict[str, Any]) -> set[str]:
    questions = state.get("clarifying_questions")
    if not isinstance(questions, list):
        return set()
    open_ids: set[str] = set()
    for item in questions:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "open")).lower()
        if status in ("resolved", "answered", "closed"):
            continue
        qid = item.get("id")
        if isinstance(qid, str) and qid.strip():
            open_ids.add(qid)
    return open_ids


def submit_clarifying_answers(
    snapshot: dict[str, Any],
    answers: dict[str, str],
) -> dict[str, Any]:
    """Record user answers for open clarifying questions; clear wait when none remain."""
    wait = snapshot.get("wait")
    if not isinstance(wait, dict):
        return {
            "ok": False,
            "code": "WAIT_KIND_MISMATCH",
            "message": "Run is not waiting for user input",
            "wait_kind": None,
        }
    wait_kind = str(wait.get("kind") or "")
    if wait_kind != "user_input":
        return {
            "ok": False,
            "code": "WAIT_KIND_MISMATCH",
            "message": f"Active wait is {wait_kind!r}; use the command matching that wait kind",
            "wait_kind": wait_kind,
        }

    state = snapshot.get("state")
    if not isinstance(state, dict):
        return {"ok": False, "code": "NO_QUESTIONS", "message": "No clarifying questions on run state"}

    open_ids = _open_question_ids(state)
    if not open_ids:
        return {"ok": False, "code": "NO_QUESTIONS", "message": "No open clarifying questions"}

    if not answers:
        return {"ok": False, "code": "ANSWERS_REQUIRED", "message": "answers must be a non-empty object"}

    stored = state.get("clarifying_answers")
    if not isinstance(stored, dict):
        stored = {}
    visit_id = str(wait.get("visit_id") or "")

    for qid, text in answers.items():
        key = str(qid)
        if key not in open_ids:
            return {
                "ok": False,
                "code": "UNKNOWN_QUESTION",
                "message": f"Question id {key!r} is not open on this run",
                "question_id": key,
            }
        if not str(text).strip():
            return {
                "ok": False,
                "code": "ANSWER_EMPTY",
                "message": f"Answer for {key!r} must not be empty",
                "question_id": key,
            }
        stored[key] = str(text).strip()

    state["clarifying_answers"] = stored
    questions = state.get("clarifying_questions")
    if isinstance(questions, list):
        for item in questions:
            if not isinstance(item, dict):
                continue
            qid = str(item.get("id") or "")
            if qid in answers:
                item["answer"] = stored[qid]
                item["status"] = "answered"

    sync_open_clarifying_questions_count(snapshot)
    open_count = derive_open_clarifying_questions_count(state)

    append_event(
        snapshot,
        event_type="user.input.submitted",
        visit_id=visit_id or None,
        payload={"answers": dict(stored), "open_clarifying_questions_count": open_count},
    )

    if open_count == 0:
        clear_run_wait(snapshot)
    else:
        set_run_wait(
            snapshot,
            kind="user_input",
            visit_id=visit_id,
            summary=f"{open_count} clarifying question(s) need answers",
            request_ref=str(wait.get("request_ref") or f"questions:{visit_id}"),
        )

    return {
        "ok": True,
        "open_clarifying_questions_count": open_count,
        "wait": snapshot.get("wait"),
    }
