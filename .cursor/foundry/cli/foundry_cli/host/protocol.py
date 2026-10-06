"""Versioned JSON control protocol for the local job host."""

from __future__ import annotations

import json
from typing import Any

from foundry_cli.host.paths import PROTOCOL_VERSION

MUTATION_METHODS = frozenset(
    {
        "run.create",
        "run.advance",
        "run.agent.submit",
        "run.answer",
        "run.decide",
        "run.start",
        "run.retry",
        "run.cancel",
        "host.stop",
    }
)


class ProtocolError(Exception):
    def __init__(self, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra


def parse_request_line(line: str) -> dict[str, Any]:
    line = line.strip()
    if not line:
        raise ProtocolError("INVALID_REQUEST", "Empty request line")
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError("INVALID_REQUEST", f"Request is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("INVALID_REQUEST", "Request must be a JSON object")
    version = payload.get("protocol_version")
    if version != PROTOCOL_VERSION:
        raise ProtocolError(
            "UNSUPPORTED_PROTOCOL",
            f"Unsupported protocol_version {version!r}; expected {PROTOCOL_VERSION}",
        )
    request_id = payload.get("id")
    if not isinstance(request_id, str) or not request_id.strip():
        raise ProtocolError("INVALID_REQUEST", "Request id is required")
    method = payload.get("method")
    if not isinstance(method, str) or not method.strip():
        raise ProtocolError("INVALID_REQUEST", "Request method is required")
    params = payload.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ProtocolError("INVALID_REQUEST", "Request params must be a JSON object")
    if method in MUTATION_METHODS:
        key = params.get("idempotency_key")
        if not isinstance(key, str) or not key.strip():
            raise ProtocolError(
                "INVALID_REQUEST",
                f"Mutation {method} requires params.idempotency_key",
            )
        if method in {
            "run.advance",
            "run.agent.submit",
            "run.answer",
            "run.decide",
            "run.start",
            "run.retry",
            "run.cancel",
        }:
            rev = params.get("expected_revision")
            if rev is None:
                raise ProtocolError(
                    "INVALID_REQUEST",
                    f"{method} requires params.expected_revision",
                )
            try:
                int(rev)
            except (TypeError, ValueError):
                raise ProtocolError(
                    "INVALID_REQUEST",
                    "expected_revision must be an integer",
                ) from None
        if method == "run.create":
            prompt = params.get("work_prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ProtocolError("INVALID_REQUEST", "run.create requires params.work_prompt")
        if method == "run.answer":
            answers = params.get("answers")
            if not isinstance(answers, dict) or not answers:
                raise ProtocolError("INVALID_REQUEST", "run.answer requires non-empty params.answers object")
        if method == "run.decide":
            decision = params.get("decision")
            if not isinstance(decision, str) or not decision.strip():
                raise ProtocolError("INVALID_REQUEST", "run.decide requires params.decision")
        if method == "run.cancel":
            reason = params.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                raise ProtocolError("INVALID_REQUEST", "run.cancel requires params.reason")
        if method == "run.agent.submit":
            request_id = params.get("request_id")
            if not isinstance(request_id, str) or not request_id.strip():
                raise ProtocolError("INVALID_REQUEST", "run.agent.submit requires params.request_id")
            if not isinstance(params.get("result"), dict):
                raise ProtocolError("INVALID_REQUEST", "run.agent.submit requires params.result object")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "id": request_id,
        "method": method,
        "params": params,
    }


def success_response(request_id: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "id": request_id,
        "ok": True,
        "result": result,
    }


def error_response(
    request_id: str,
    code: str,
    message: str,
    **extra: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "id": request_id,
        "ok": False,
        "error": {"code": code, "message": message},
    }
    if extra:
        body["error"].update(extra)
    return body


def encode_response(response: dict[str, Any]) -> bytes:
    return (json.dumps(response, sort_keys=True) + "\n").encode("utf-8")
