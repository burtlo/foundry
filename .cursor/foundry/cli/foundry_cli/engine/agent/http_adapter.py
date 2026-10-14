"""Optional HTTP adapter hook (env-gated; not used in CI)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any

from foundry_cli.engine.agent.adapter import AgentAdapterEnvelope
from foundry_cli.judgment_bridge.diagnostics import JudgmentAdapterFailure


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
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            hint = "Run foundry up and verify judgment bridge health"
            layer = "bridge"
            upstream_from_body: int | None = None
            try:
                parsed = json.loads(body) if body.strip() else {}
                diag = parsed.get("diagnostics") if isinstance(parsed, dict) else None
                if isinstance(diag, dict):
                    hint = str(diag.get("recovery_hint") or hint)
                    layer = str(diag.get("layer") or layer)
                    raw_upstream = diag.get("upstream_status")
                    if raw_upstream is not None:
                        upstream_from_body = int(raw_upstream)
            except (json.JSONDecodeError, TypeError, ValueError):
                parsed = {}
            upstream_status = upstream_from_body if upstream_from_body is not None else int(exc.code)
            message = (
                f"Agent HTTP adapter ({layer}) failed HTTP {exc.code}: {body[:500]}. {hint}"
            )
            if upstream_from_body is not None:
                message = f"{message} (upstream_status={upstream_from_body})"
            raise JudgmentAdapterFailure(
                message,
                diagnostics={
                    "layer": layer,
                    "recovery_hint": hint,
                    "upstream_status": upstream_status,
                },
                http_status=int(exc.code),
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Agent HTTP adapter (bridge) failed: {exc}. Run foundry up and verify bridge reachability"
            ) from exc
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
