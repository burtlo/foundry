"""Optional HTTP adapter hook (env-gated; not used in CI)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any

from foundry_cli.engine.agent.adapter import AgentAdapterEnvelope


class HttpAgentAdapter:
    """POST immutable request JSON to FOUNDRY_AGENT_HTTP_URL; expects envelope JSON."""

    def invoke(self, request: dict[str, Any]) -> AgentAdapterEnvelope:
        url = os.environ.get("FOUNDRY_AGENT_HTTP_URL")
        if not url:
            raise RuntimeError("FOUNDRY_AGENT_HTTP_URL is required for http adapter")
        body = json.dumps({"request": request}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=int(request.get("limits", {}).get("timeout_seconds") or 120)) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Agent HTTP adapter failed: {exc}") from exc
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise RuntimeError("Agent HTTP adapter response missing result object")
        return AgentAdapterEnvelope(
            request_id=str(request["request_id"]),
            attempt=int(request.get("attempt") or 1),
            provider_request_id=str(payload.get("provider_request_id") or f"http_{uuid.uuid4().hex[:12]}"),
            raw_response_ref=payload.get("raw_response_ref") if isinstance(payload, dict) else None,
            usage=payload.get("usage") if isinstance(payload.get("usage"), dict) else {},
            finish_reason=str(payload.get("finish_reason") or "stop"),
            result=result,
        )
