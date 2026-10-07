"""API key resolution for the judgment bridge."""

from __future__ import annotations

import os


def resolve_cursor_api_key() -> str:
    for name in ("FOUNDRY_CURSOR_API_KEY", "CURSOR_API_KEY"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    raise RuntimeError(
        "Judgment bridge requires FOUNDRY_CURSOR_API_KEY or CURSOR_API_KEY in the environment"
    )
