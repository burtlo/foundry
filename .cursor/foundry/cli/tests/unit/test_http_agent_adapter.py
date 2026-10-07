"""HttpAgentAdapter and get_adapter() production gating."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from foundry_cli.engine.agent.adapter import (
    StubAgentAdapter,
    default_stub_verify_acceptance_result,
    get_adapter,
)
from foundry_cli.engine.agent.http_adapter import HttpAgentAdapter


def _sample_request() -> dict:
    return {
        "request_id": "ar_test1234567890",
        "attempt": 2,
        "task_id": "shape.examine",
        "limits": {"timeout_seconds": 30},
    }


def _mock_urlopen_response(payload: dict) -> MagicMock:
    body = json.dumps(payload).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def test_http_adapter_posts_request_and_maps_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_AGENT_HTTP_URL", "https://agent.example/invoke")
    request = _sample_request()
    server_payload = {
        "provider_request_id": "cloud-run-1",
        "raw_response_ref": "run:artifacts/raw-1",
        "usage": {"input_tokens": 100, "output_tokens": 50},
        "finish_reason": "stop",
        "result": {"summary": "Examination complete", "questions": []},
    }
    adapter = HttpAgentAdapter()

    with patch("urllib.request.urlopen") as urlopen_mock:
        urlopen_mock.return_value = _mock_urlopen_response(server_payload)
        envelope = adapter.invoke(request)

    urlopen_mock.assert_called_once()
    http_req = urlopen_mock.call_args[0][0]
    assert http_req.full_url == "https://agent.example/invoke"
    assert http_req.method == "POST"
    posted = json.loads(http_req.data.decode("utf-8"))
    assert posted == {"request": request}
    assert urlopen_mock.call_args[1]["timeout"] == 30

    assert envelope.request_id == "ar_test1234567890"
    assert envelope.attempt == 2
    assert envelope.provider_request_id == "cloud-run-1"
    assert envelope.raw_response_ref == "run:artifacts/raw-1"
    assert envelope.usage == {"input_tokens": 100, "output_tokens": 50}
    assert envelope.finish_reason == "stop"
    assert envelope.result == server_payload["result"]


def test_http_adapter_urlopen_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_AGENT_HTTP_URL", "https://agent.example/invoke")
    adapter = HttpAgentAdapter()

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
        with pytest.raises(RuntimeError, match="Agent HTTP adapter failed"):
            adapter.invoke(_sample_request())


def test_http_adapter_missing_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_AGENT_HTTP_URL", "https://agent.example/invoke")
    adapter = HttpAgentAdapter()

    with patch("urllib.request.urlopen", return_value=_mock_urlopen_response({"finish_reason": "stop"})):
        with pytest.raises(RuntimeError, match="missing result"):
            adapter.invoke(_sample_request())


def test_http_adapter_requires_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDRY_AGENT_HTTP_URL", raising=False)
    adapter = HttpAgentAdapter()
    with pytest.raises(RuntimeError, match="FOUNDRY_AGENT_HTTP_URL is required"):
        adapter.invoke(_sample_request())


def test_get_adapter_requires_explicit_config_outside_stub_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDRY_AGENT_ADAPTER", raising=False)
    monkeypatch.delenv("FOUNDRY_ALLOW_STUB_ADAPTER", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    with pytest.raises(RuntimeError, match="No agent adapter configured"):
        get_adapter()


def test_get_adapter_http_returns_http_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_AGENT_ADAPTER", "http")
    monkeypatch.setenv("FOUNDRY_AGENT_HTTP_URL", "https://agent.example/invoke")

    adapter = get_adapter()
    assert isinstance(adapter, HttpAgentAdapter)


def test_get_adapter_stub_when_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_AGENT_ADAPTER", "stub")
    monkeypatch.delenv("FOUNDRY_ALLOW_STUB_ADAPTER", raising=False)

    adapter = get_adapter()
    assert isinstance(adapter, StubAgentAdapter)


def test_stub_verify_acceptance_pass_without_execute_stub_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production stub path for verify must not honor FOUNDRY_VERIFY_ACCEPTANCE_DECISION without execute stub."""
    monkeypatch.delenv("FOUNDRY_EXECUTE_STUB", raising=False)
    monkeypatch.setenv("FOUNDRY_VERIFY_ACCEPTANCE_DECISION", "replan")

    result = default_stub_verify_acceptance_result()
    assert result["gate_decision"] == "pass"
    assert result["evidence_ok"] is True
