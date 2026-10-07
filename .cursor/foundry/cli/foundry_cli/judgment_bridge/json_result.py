"""Parse structured task results from model text."""

from __future__ import annotations

import json
import re
from typing import Any

_JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*([\s\S]*?)\s*```",
    re.IGNORECASE,
)


def parse_json_result_object(text: str) -> dict[str, Any]:
    """Return a JSON object from raw model output (optionally fenced)."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Model returned empty output")
    fence = _JSON_FENCE_RE.search(raw)
    if fence:
        raw = fence.group(1).strip()
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Model output must be a JSON object")
    return parsed
