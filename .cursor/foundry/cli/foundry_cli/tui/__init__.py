"""Textual TUI for the Foundry job host (host-only client)."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.tui.app import run_tui


def run_interactive_attach(
    *,
    workspace: Path,
    registry: str | None = None,
    run_id: str | None = None,
) -> None:
    """Launch interactive attach: run list when ``run_id`` is omitted, else run detail."""
    run_tui(workspace=workspace, registry=registry, run_id=run_id)


__all__ = ["run_interactive_attach", "run_tui"]
