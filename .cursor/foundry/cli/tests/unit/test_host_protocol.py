"""Unit tests for job host protocol parsing and handlers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from foundry_cli.host.handlers import HostHandlers
from foundry_cli.host.protocol import ProtocolError, parse_request_line
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT


def test_parse_request_rejects_missing_idempotency_on_advance() -> None:
    payload = {
        "protocol_version": 1,
        "id": "req-1",
        "method": "run.advance",
        "params": {"expected_revision": 1, "run_id": "x"},
    }
    with pytest.raises(ProtocolError) as exc:
        parse_request_line(json.dumps(payload))
    assert exc.value.code == "INVALID_REQUEST"


def test_parse_request_accepts_valid_agent_submit() -> None:
    payload = {
        "protocol_version": 1,
        "id": "req-2",
        "method": "run.agent.submit",
        "params": {
            "expected_revision": 3,
            "idempotency_key": "key-2",
            "request_id": "ar_abc",
            "result": _valid_result_minimal(),
        },
    }
    parsed = parse_request_line(json.dumps(payload))
    assert parsed["method"] == "run.agent.submit"


def _valid_result_minimal() -> dict:
    return {
        "summary": "s",
        "draft_acceptance_criteria": ["ac"],
        "assumptions": [],
        "questions": [],
        "decisions": [{"text": "d", "basis": "b"}],
    }


def test_parse_request_accepts_valid_advance() -> None:
    payload = {
        "protocol_version": 1,
        "id": "req-1",
        "method": "run.advance",
        "params": {
            "expected_revision": 2,
            "idempotency_key": "key-1",
            "run_id": "adv-0001",
        },
    }
    parsed = parse_request_line(json.dumps(payload))
    assert parsed["method"] == "run.advance"
    assert parsed["params"]["idempotency_key"] == "key-1"


def test_handler_health(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    handlers = HostHandlers(workspace, BUNDLE)
    result = handlers.health()
    assert result.get("ok") is True
    assert result.get("status") == "ready"


def test_handler_run_get_missing_run(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    handlers = HostHandlers(workspace, BUNDLE)
    result = handlers.run_get({"run_id": "missing"})
    assert result.get("ok") is False
    assert result.get("error", {}).get("code") == "RUN_NOT_FOUND"


def test_parse_request_accepts_run_answer() -> None:
    payload = {
        "protocol_version": 1,
        "id": "req-answer",
        "method": "run.answer",
        "params": {
            "expected_revision": 2,
            "idempotency_key": "key-answer",
            "run_id": "adv-0001",
            "answers": {"q1": "yes"},
        },
    }
    parsed = parse_request_line(json.dumps(payload))
    assert parsed["method"] == "run.answer"


def test_advance_idempotency_cached(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    handlers = HostHandlers(workspace, BUNDLE)
    params = {
        "expected_revision": 1,
        "idempotency_key": "same-key",
        "run_id": "nope",
    }
    first = handlers.dispatch("run.advance", params, "r1")
    second = handlers.dispatch("run.advance", params, "r2")
    assert first == second
