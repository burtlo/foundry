"""Judgment bridge HTTP contract and helpers."""

from __future__ import annotations

import json
from http.client import HTTPConnection
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest

from foundry_cli.judgment_bridge.json_result import parse_json_result_object
from foundry_cli.judgment_bridge.keys import resolve_cursor_api_key
from foundry_cli.judgment_bridge.server import JudgmentBridgeHandler
from http.server import ThreadingHTTPServer
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT


def test_parse_json_result_object_raw() -> None:
    parsed = parse_json_result_object('{"summary": "ok", "questions": []}')
    assert parsed["summary"] == "ok"


def test_parse_json_result_object_fenced() -> None:
    text = 'Here is output:\n```json\n{"verdict": "PROCEED"}\n```'
    assert parse_json_result_object(text)["verdict"] == "PROCEED"


def test_resolve_cursor_api_key_prefers_foundry_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_CURSOR_API_KEY", "foundry-key")
    monkeypatch.setenv("CURSOR_API_KEY", "cursor-key")
    assert resolve_cursor_api_key() == "foundry-key"


def test_http_bridge_invokes_provider(tmp_path) -> None:
    examination = {
        "summary": "Bridge test examination",
        "draft_acceptance_criteria": ["Ship feature"],
        "assumptions": [],
        "questions": [],
        "decisions": [{"text": "Proceed", "basis": "test"}],
    }

    def fake_invoke(request, *, workspace, foundry_bundle):  # noqa: ANN001
        assert request["task_id"] == "shape.examine"
        return {
            "provider_request_id": "run_test",
            "finish_reason": "stop",
            "usage": {},
            "result": examination,
        }

    class Handler(JudgmentBridgeHandler):
        pass

    Handler.workspace = tmp_path
    Handler.foundry_bundle = BUNDLE
    Handler.agent_path = "/v1/agent"

    port = 18791
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    with patch(
        "foundry_cli.judgment_bridge.server.invoke_judgment",
        side_effect=fake_invoke,
    ):
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request(
                "POST",
                "/v1/agent",
                json.dumps(
                    {
                        "request": {
                            "request_id": "ar_test",
                            "task_id": "shape.examine",
                            "instructions": "Examine",
                            "input": {},
                            "output_schema": "registry:schemas/shape-examination-result.schema.json",
                        }
                    }
                ),
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            body = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
            assert body["result"]["summary"] == examination["summary"]
        finally:
            server.shutdown()


@pytest.mark.parametrize("sdk_status", ["completed", "finished"])
@patch("cursor_sdk.Agent")
def test_cursor_provider_validates_schema(
    mock_agent: MagicMock, tmp_path, monkeypatch, sdk_status: str
) -> None:
    from foundry_cli.judgment_bridge.cursor_provider import invoke_judgment

    monkeypatch.setenv("FOUNDRY_CURSOR_API_KEY", "test-key")
    mock_agent.prompt.return_value = MagicMock(
        status=sdk_status,
        result=json.dumps(
            {
                "summary": "s",
                "draft_acceptance_criteria": ["a"],
                "assumptions": [],
                "questions": [],
                "decisions": [],
            }
        ),
        id="run_1",
        usage=None,
    )
    request = {
        "task_id": "shape.examine",
        "instructions": "Do examine",
        "input": {},
        "output_schema": "registry:schemas/shape-examination-result.schema.json",
        "limits": {"timeout_seconds": 30},
    }
    body = invoke_judgment(request, workspace=tmp_path, foundry_bundle=BUNDLE)
    assert body["result"]["summary"] == "s"
    mock_agent.prompt.assert_called_once()
