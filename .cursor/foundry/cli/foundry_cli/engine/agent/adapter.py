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


def default_stub_presentation_result() -> dict[str, Any]:
    return {
        "summary": "PROCEED: presentation ready to publish (stub).",
        "verdict": "PROCEED",
        "presented_ac": "Deliver the requested capability with tests.",
        "presentation_markdown": (
            "# Shape plan presentation\n\n"
            "## Acceptance criteria\n\n"
            "Deliver the requested capability with tests.\n"
        ),
    }


def default_stub_record_result() -> dict[str, Any]:
    return {
        "summary": "PROCEED: plan ready to publish (stub).",
        "verdict": "PROCEED",
        "approved_ac": "Deliver the requested capability with tests.",
        "plan_markdown": (
            "# Living plan\n\n"
            "## Scope\n\n"
            "Stub living plan.\n\n"
            "## Acceptance criteria\n\n"
            "Deliver the requested capability with tests.\n"
        ),
    }


class StubAgentAdapter:
    """Deterministic adapter for tests and local development."""

    def __init__(self, *, default_result: dict[str, Any] | None = None) -> None:
        self._default_result = default_result
        self.invoke_count = 0

    def invoke(self, request: dict[str, Any]) -> AgentAdapterEnvelope:
        self.invoke_count += 1
        override = os.environ.get("FOUNDRY_AGENT_STUB_RESULT")
        if override:
            result = json.loads(override)
        elif self._default_result is not None:
            result = self._default_result
        else:
            task_id = str(request.get("task_id") or "")
            if task_id == "shape.present":
                result = default_stub_presentation_result()
            elif task_id == "shape.record":
                result = default_stub_record_result()
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


def _stub_adapter_allowed() -> bool:
    flag = (os.environ.get("FOUNDRY_ALLOW_STUB_ADAPTER") or "").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def get_adapter() -> AgentAdapter:
    kind = (os.environ.get("FOUNDRY_AGENT_ADAPTER") or "").strip().lower()
    if not kind:
        if _stub_adapter_allowed():
            kind = "stub"
        else:
            raise RuntimeError(
                "No agent adapter configured for user-mode runs. Set FOUNDRY_AGENT_ADAPTER "
                "to 'http' (and FOUNDRY_AGENT_HTTP_URL) or another supported adapter. "
                "For local development/tests only, set FOUNDRY_ALLOW_STUB_ADAPTER=1."
            )
    if kind == "stub":
        return StubAgentAdapter()
    if kind == "http":
        from foundry_cli.engine.agent.http_adapter import HttpAgentAdapter

        return HttpAgentAdapter()
    raise ValueError(f"Unsupported FOUNDRY_AGENT_ADAPTER: {kind!r}")
