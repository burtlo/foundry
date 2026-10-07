"""Unit tests for examination state derivation."""

from __future__ import annotations

from foundry_cli.engine.examination_state import derive_open_clarifying_questions_count
from foundry_cli.engine.routing import evaluate_when_expression
from tests.unit.constants import OPEN_CLARIFYING_QUESTIONS_NONZERO, OPEN_CLARIFYING_QUESTIONS_ZERO, VISIT_V002
from tests.unit.helpers import make_visit


def test_derive_open_questions_from_structured_list() -> None:
    state = {
        "clarifying_questions": [
            {"text": "Q1", "status": "open"},
            {"text": "Q2", "status": "resolved"},
        ],
        "open_clarifying_questions_count": 99,
    }
    assert derive_open_clarifying_questions_count(state) == 1


def test_routing_uses_derived_open_question_count() -> None:
    visit = make_visit(VISIT_V002)
    snapshot = {
        "state": {
            "clarifying_questions": [{"text": "Q1", "status": "open"}],
            "open_clarifying_questions_count": 0,
        }
    }
    assert evaluate_when_expression(snapshot, visit, OPEN_CLARIFYING_QUESTIONS_ZERO) is False
    assert evaluate_when_expression(snapshot, visit, OPEN_CLARIFYING_QUESTIONS_NONZERO) is True
