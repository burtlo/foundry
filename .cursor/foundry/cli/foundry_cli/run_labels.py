"""Stable labels derived from run snapshot fields (CLI / host / TUI)."""

from __future__ import annotations


def phase_label(node_id: str) -> str:
    if node_id.startswith("shape."):
        return "shape"
    if node_id.startswith("execute."):
        return "execute"
    if node_id.startswith("implement."):
        return "implement"
    if node_id.startswith("verify."):
        return "verify"
    if node_id == "deliver.stub":
        return "deliver"
    return "unknown"
