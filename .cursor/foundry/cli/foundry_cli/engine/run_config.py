"""Run snapshot config helpers shared by advance and mechanism actions."""

from __future__ import annotations

from typing import Any


def work_prompt_from_snapshot(snapshot: dict[str, Any]) -> str | None:
    config = snapshot.get("config")
    if isinstance(config, dict):
        shape = config.get("shape")
        if isinstance(shape, dict):
            prompt = shape.get("work_prompt")
            if isinstance(prompt, str) and prompt.strip():
                return prompt
        direct = config.get("work_prompt")
        if isinstance(direct, str) and direct.strip():
            return direct
    state = snapshot.get("state")
    if isinstance(state, dict):
        prompt = state.get("work_prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt
    return None
