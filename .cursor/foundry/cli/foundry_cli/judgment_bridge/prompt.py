"""Prompt assembly for judgment tasks."""

from __future__ import annotations

import json
from typing import Any


def build_judgment_prompt(request: dict[str, Any]) -> str:
    """Combine instructions, input, and schema contract for the Cursor agent."""
    instructions = str(request.get("instructions") or "").strip()
    task_id = str(request.get("task_id") or "")
    output_schema = str(request.get("output_schema") or "")
    input_body = request.get("input")
    if not isinstance(input_body, dict):
        input_body = {}

    input_json = json.dumps(input_body, indent=2, sort_keys=True)
    return (
        f"You are executing Foundry judgment task `{task_id}`.\n\n"
        "## Instructions\n\n"
        f"{instructions}\n\n"
        "## Input (JSON)\n\n"
        f"{input_json}\n\n"
        "## Output contract\n\n"
        "Respond with **only** a single JSON object (no prose) that validates against "
        f"schema ref `{output_schema}`. "
        "Do not wrap in markdown unless unavoidable; prefer raw JSON."
    )
