"""Cursor SDK provider for judgment tasks."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from foundry_cli.judgment_bridge.json_result import parse_json_result_object
from foundry_cli.judgment_bridge.keys import resolve_cursor_api_key
from foundry_cli.judgment_bridge.prompt import build_judgment_prompt
from foundry_cli.judgment_bridge.validate import validate_task_result

JUDGMENT_TASK_IDS = frozenset(
    {
        "shape.examine",
        "shape.present",
        "shape.record",
        "execute.plan",
        "verify.acceptance",
    }
)


def _default_model() -> str:
    return (os.environ.get("FOUNDRY_CURSOR_MODEL") or "composer-2.5").strip()


def invoke_judgment(
    request: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
) -> dict[str, Any]:
    """
    Call Cursor SDK and return an HttpAgentAdapter-compatible response body
    (without request_id / attempt — caller adds envelope fields).
    """
    task_id = str(request.get("task_id") or "")
    if task_id not in JUDGMENT_TASK_IDS:
        raise ValueError(f"Unsupported judgment task_id: {task_id!r}")

    try:
        from cursor_sdk import Agent
        from cursor_sdk.types import AgentOptions, LocalAgentOptions
    except ImportError as exc:
        raise RuntimeError(
            "cursor-sdk is not installed; pip install cursor-sdk or use the CLI venv with bridge extras"
        ) from exc

    api_key = resolve_cursor_api_key()
    prompt = build_judgment_prompt(request)
    limits = request.get("limits") if isinstance(request.get("limits"), dict) else {}
    timeout_seconds = int(limits.get("timeout_seconds") or 120)

    options = AgentOptions(
        api_key=api_key,
        model=_default_model(),
        local=LocalAgentOptions(cwd=str(workspace.resolve())),
    )

    run_result = Agent.prompt(prompt, options)
    status = str(getattr(run_result, "status", "") or "")
    if status and status.lower() not in ("completed", "succeeded", "success", "done"):
        raise RuntimeError(f"Cursor agent run failed with status {status!r}")

    text = str(getattr(run_result, "result", "") or "")
    parsed = parse_json_result_object(text)
    validate_task_result(request, parsed, foundry_bundle=foundry_bundle)

    usage_obj = getattr(run_result, "usage", None)
    usage: dict[str, Any] = {}
    if usage_obj is not None:
        usage = {
            "input_tokens": getattr(usage_obj, "input_tokens", None) or 0,
            "output_tokens": getattr(usage_obj, "output_tokens", None) or 0,
        }

    return {
        "provider_request_id": str(getattr(run_result, "id", "") or f"cursor_{uuid.uuid4().hex[:12]}"),
        "finish_reason": "stop",
        "usage": usage,
        "result": parsed,
    }
