"""Agent provider adapters (stub default for CI)."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentAdapterEnvelope:
    request_id: str
    attempt: int
    provider_request_id: str
    raw_response_ref: str | None
    usage: dict[str, Any]
    finish_reason: str
    result: dict[str, Any]


class AgentAdapter(Protocol):
    def invoke(self, request: dict[str, Any]) -> AgentAdapterEnvelope:
        """Call the model provider for an immutable agent request."""


def default_stub_examination_result() -> dict[str, Any]:
    return {
        "summary": "Examination stub: request understood with no open questions.",
        "draft_acceptance_criteria": ["Deliver the requested capability with tests."],
        "assumptions": ["Existing app manifest and registry are authoritative."],
        "questions": [],
        "decisions": [
            {
                "text": "Proceed with draft AC as stated.",
                "basis": "Stub adapter default for CI.",
            }
        ],
    }


class StubAgentAdapter:
    """Deterministic adapter for tests and local development."""

    def __init__(self, *, default_result: dict[str, Any] | None = None) -> None:
        self._default_result = default_result

    def invoke(self, request: dict[str, Any]) -> AgentAdapterEnvelope:
        override = os.environ.get("FOUNDRY_AGENT_STUB_RESULT")
        if override:
            result = json.loads(override)
        elif self._default_result is not None:
            result = self._default_result
        else:
            result = default_stub_examination_result()
        return AgentAdapterEnvelope(
            request_id=str(request["request_id"]),
            attempt=int(request.get("attempt") or 1),
            provider_request_id=f"stub_{uuid.uuid4().hex[:12]}",
            raw_response_ref=None,
            usage={"input_tokens": 0, "output_tokens": 0},
            finish_reason="stop",
            result=result,
        )


def get_adapter() -> AgentAdapter:
    kind = (os.environ.get("FOUNDRY_AGENT_ADAPTER") or "stub").strip().lower()
    if kind == "stub":
        return StubAgentAdapter()
    if kind == "http":
        from foundry_cli.engine.agent.http_adapter import HttpAgentAdapter

        return HttpAgentAdapter()
    raise ValueError(f"Unsupported FOUNDRY_AGENT_ADAPTER: {kind!r}")
